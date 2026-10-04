import { allowedMethods } from './paths';
import { recordRequest } from './requests';

export function normalizeUrl(value: string): string {
  if (value.startsWith('//') || /[\\#]/.test(value)) throw new Error('Unrecognized backend URL');
  const rawPath = value.replace(/^https?:\/\/[^/]+/i, '').split('?')[0];
  if (rawPath.includes('%') || rawPath.includes('..')) throw new Error('Unsafe backend path');
  const url = new URL(value, 'http://console.invalid');
  if (!['http:', 'https:'].includes(url.protocol)) throw new Error('Unsupported URL protocol');
  const path = url.pathname.replace(/^\/api(?=\/|$)/, '').replace(/^\//, '');
  if (!allowedMethods(path)) throw new Error('Unrecognized backend path');
  return '/api/' + path + url.search;
}
export class ApiError extends Error {
  constructor(public status: number, public body: unknown) {
    const detail = body && typeof body === 'object' && 'detail' in body ? body.detail : body;
    super(`HTTP ${status}: ${typeof detail === 'string' ? detail : JSON.stringify(detail)}`);
  }
}
type Options = RequestInit & { polling?: boolean; binary?: boolean; maxBytes?: number };
async function boundedBlob(response: Response, maxBytes: number): Promise<Blob> {
  const reader = response.body?.getReader();
  if (!reader) return new Blob();
  const chunks: Uint8Array<ArrayBuffer>[] = [];
  let received = 0;
  try {
    while (true) {
      const { done, value } = await reader.read();
      if (done) break;
      received += value.byteLength;
      if (received > maxBytes) {
        await reader.cancel();
        throw new Error(`Preview limited to ${Math.round(maxBytes / 1024 / 1024)} MiB; use download.`);
      }
      chunks.push(new Uint8Array(value));
    }
    return new Blob(chunks);
  } finally { reader.releaseLock(); }
}
export async function api<T = unknown>(url: string, options: Options = {}): Promise<T> {
  const path = normalizeUrl(url);
  const { polling = false, binary = false, maxBytes = 20 * 1024 * 1024, ...init } = options;
  const start = performance.now();
  let status: number | null = null;
  let result: unknown;
  try {
    const response = await fetch(path, { ...init, credentials: 'omit', redirect: 'error' });
    status = response.status;
    if (binary && response.ok) result = await boundedBlob(response, maxBytes);
    else {
      const text = await response.text();
      try { result = text ? JSON.parse(text) : null; } catch { result = text; }
    }
    if (!response.ok) throw new ApiError(status, result);
    return result as T;
  } catch (error) {
    if (status === null || result === undefined) result = error instanceof Error ? error.message : String(error);
    throw error;
  } finally {
    recordRequest({ path, method: init.method ?? 'GET', status, ms: Math.round(performance.now() - start), request: init.body, response: result, polling });
  }
}
export function jsonBody(value: unknown): Pick<RequestInit, 'body' | 'headers'> {
  return { body: JSON.stringify(value), headers: { 'content-type': 'application/json' } };
}
