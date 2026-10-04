import { api, jsonBody, normalizeUrl } from './api';
export async function reserve(filename: string, size_bytes: number): Promise<string> {
  const result = await api<{ upload_url: string }>('/images/uploads', { method: 'POST', ...jsonBody({ filename, size_bytes }) });
  return normalizeUrl(result.upload_url);
}
export async function send(url: string, file: File): Promise<void> {
  await api(url, { method: 'PUT', body: file, headers: { 'content-type': 'application/octet-stream' } });
}
export async function upload(file: File, filename = file.name, size = file.size): Promise<string> {
  const url = await reserve(filename, size);
  await send(url, file);
  return url;
}
