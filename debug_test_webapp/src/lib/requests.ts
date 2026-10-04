import { writable } from 'svelte/store';
export interface RequestEntry {
  id: number; at: string; method: string; path: string; status: number | null; ms: number;
  request: string; response: string; polling: boolean;
}
export const requestLog = writable<RequestEntry[]>([]);
let sequence = 0;
function summarize(value: unknown): string {
  if (value instanceof Blob || value instanceof ArrayBuffer || ArrayBuffer.isView(value) || value instanceof ReadableStream) return '[binary omitted]';
  const text = typeof value === 'string' ? value : JSON.stringify(value ?? null);
  return text.length > 4096 ? text.slice(0, 4096) + '\n… [truncated]' : text;
}
export function recordRequest(entry: Omit<RequestEntry, 'id' | 'at' | 'request' | 'response'> & { request?: unknown; response?: unknown }) {
  requestLog.update(entries => [{ ...entry, id: ++sequence, at: new Date().toISOString(), request: summarize(entry.request), response: summarize(entry.response) }, ...entries].slice(0, 100));
}
export function clearRequests() { requestLog.set([]); }
