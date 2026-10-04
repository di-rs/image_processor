import { describe, it, expect, vi, afterEach } from 'vitest';
import { normalizeUrl, api, ApiError } from '../src/lib/api';
import { requestLog, recordRequest, clearRequests } from '../src/lib/requests';
import { get } from 'svelte/store';
import { proxy } from '../src/lib/server/proxy';
import { reserve, send, upload } from '../src/lib/upload';
import { rasterType } from '../src/lib/preview';

afterEach(() => { vi.unstubAllGlobals(); clearRequests(); });
describe('same-origin API and bounded diagnostics', () => {
  it('normalizes only recognized paths, never external fetches', () => {
    expect(normalizeUrl('http://api:8000/images/uploads/abc-123')).toBe('/api/images/uploads/abc-123');
    expect(normalizeUrl('https://other.test/images/4/original')).toBe('/api/images/4/original');
    expect(normalizeUrl('/api/debug/images?status=queued&status=processing')).toBe('/api/debug/images?status=queued&status=processing');
    for (const value of ['https://evil.test/steal', '//evil.test/images/1', '/images/%2e%2e/health', '/images/../health', 'javascript:alert(1)', '/images/1#x']) expect(() => normalizeUrl(value)).toThrow();
  });
  it.each([
    [422, JSON.stringify({ detail: [{ loc: ['body', 'size_bytes'], msg: 'must be positive' }] }), 'must be positive'],
    [409, JSON.stringify({ detail: 'Uploading' }), 'Uploading'],
    [500, 'Internal Server Error', 'Internal Server Error']
  ])('preserves %s error details in client and inspector', async (status, body, text) => {
    vi.stubGlobal('fetch', async () => new Response(body, { status }));
    await expect(api('/images/1')).rejects.toMatchObject({ status, message: expect.stringContaining(text) });
    expect(get(requestLog)[0]).toMatchObject({ status, method: 'GET' });
  });
  it('bounds history and bodies, excludes binary content', () => {
    for (let i = 0; i < 105; i++) recordRequest({ method: 'PUT', path: '/api/images/uploads/x', status: 204, ms: 1, request: new Blob(['secret']), response: 'x'.repeat(10000), polling: false });
    const entries = get(requestLog);
    expect(entries).toHaveLength(100);
    expect(entries[0].request).toBe('[binary omitted]');
    expect(entries[0].response.length).toBeLessThan(4200);
  });
});
describe('restricted streaming proxy', () => {
  const request = (path: string, method = 'GET') => new Request('http://localhost/api/' + path, { method, headers: { cookie: 'secret=x', authorization: 'Bearer secret' } });
  it.each(['%2e%2e/health', 'images/%252e%252e/health', 'images/%2f1', 'images/1/../2', 'https://evil.test', 'unknown', 'images/1\\original'])('rejects raw unsafe path %s', async (path) => {
    const upstream = vi.fn();
    const response = await proxy(request('health'), path, 'http://api:8000', upstream);
    expect(response.status).toBe(400);
    expect(upstream).not.toHaveBeenCalled();
  });
  it('rejects methods outside endpoint allowlist', async () => {
    expect((await proxy(request('debug/images', 'DELETE'), 'debug/images', 'http://api:8000')).status).toBe(405);
  });
  it('forwards repeated queries and strips credentials; preserves errors', async () => {
    let seen = '';
    const upstream = vi.fn(async (url: string | URL | Request, init?: RequestInit) => {
      seen = String(url);
      expect(new Headers(init?.headers).has('cookie')).toBe(false);
      expect(new Headers(init?.headers).has('authorization')).toBe(false);
      expect(init?.redirect).toBe('manual');
      return new Response('backend failure', { status: 422 });
    });
    const response = await proxy(request('debug/images?status=queued&status=processing&limit=20'), 'debug/images', 'http://api:8000', upstream);
    expect(seen).toBe('http://api:8000/debug/images?status=queued&status=processing&limit=20');
    expect(response.status).toBe(422);
    expect(await response.text()).toBe('backend failure');
  });
  it('streams raw PUT bytes and returns attachment without cookies', async () => {
    const req = new Request('http://localhost/api/images/uploads/key', { method: 'PUT', body: new Uint8Array([0, 1, 2]) });
    const upstream = async (_url: string | URL | Request, init?: RequestInit) => {
      expect(init?.body).toBe(req.body);
      expect(Array.from(new Uint8Array(await new Response(init?.body).arrayBuffer()))).toEqual([0, 1, 2]);
      return new Response(null, { status: 204, headers: { 'set-cookie': 'bad=1' } });
    };
    const response = await proxy(req, 'images/uploads/key', 'http://api:8000', upstream);
    expect(response.status).toBe(204);
    expect(response.headers.has('set-cookie')).toBe(false);
  });
  it('blocks upstream redirects', async () => {
    const response = await proxy(request('health'), 'health', 'http://api:8000', async () => Response.redirect('https://evil.test'));
    expect(response.status).toBe(502);
    expect(response.headers.has('location')).toBe(false);
  });
  it('reports unreachable and timeout without leaking configuration', async () => {
    expect((await proxy(request('health'), 'health', 'http://api:8000', async () => { throw new Error('secret'); })).status).toBe(502);
    const response = await proxy(request('health'), 'health', 'http://api:8000', async (_url, init) => new Promise((_resolve, reject) => init?.signal?.addEventListener('abort', () => reject(init.signal?.reason))), 5);
    expect(response.status).toBe(504);
    expect(await response.text()).not.toContain('api:8000');
  });
});
describe('bounded binary previews', () => {
  it('stops reading an oversized response instead of buffering the whole image', async () => {
    let canceled = false;
    const stream = new ReadableStream<Uint8Array>({
      start(controller) { controller.enqueue(new Uint8Array(4)); controller.enqueue(new Uint8Array(4)); controller.enqueue(new Uint8Array(4)); controller.close(); },
      cancel() { canceled = true; }
    });
    vi.stubGlobal('fetch', async () => new Response(stream));
    await expect(api('/images/1/original', { binary: true, maxBytes: 6 })).rejects.toThrow('Preview limited');
    expect(canceled).toBe(true);
  });
  it('returns a complete small image blob', async () => {
    vi.stubGlobal('fetch', async () => new Response(new Uint8Array([1, 2, 3])));
    const blob = await api<Blob>('/images/1/original', { binary: true, maxBytes: 6 });
    expect(Array.from(new Uint8Array(await blob.arrayBuffer()))).toEqual([1, 2, 3]);
  });
});

describe('uploads never retry or send before reservation', () => {
  it('reserves declared metadata then sends unmodified bytes', async () => {
    const calls: string[] = [];
    vi.stubGlobal('fetch', async (url: string, init?: RequestInit) => {
      calls.push(init?.method + ' ' + url);
      if (init?.method === 'POST') {
        expect(JSON.parse(String(init.body))).toEqual({ filename: 'negative.png', size_bytes: 2 });
        return Response.json({ upload_url: 'http://api:8000/images/uploads/key' }, { status: 201 });
      }
      expect(await new Response(init?.body).text()).toBe('abc');
      return new Response(null, { status: 204 });
    });
    await upload(new File(['abc'], 'a.png'), 'negative.png', 2);
    expect(calls).toEqual(['POST /api/images/uploads', 'PUT /api/images/uploads/key']);
  });
  it('does not send or retry when reservation fails', async () => {
    const fetcher = vi.fn(async () => Response.json({ detail: 'bad size' }, { status: 422 }));
    vi.stubGlobal('fetch', fetcher);
    await expect(upload(new File(['abc'], 'a.png'))).rejects.toBeInstanceOf(ApiError);
    expect(fetcher).toHaveBeenCalledTimes(1);
  });
  it('supports reserve-only and manual send; failed send is not retried', async () => {
    const fetcher = vi.fn(async (_url: string, init?: RequestInit) => init?.method === 'POST' ? Response.json({ upload_url: '/images/uploads/key' }, { status: 201 }) : Response.json({ detail: 'expired' }, { status: 410 }));
    vi.stubGlobal('fetch', fetcher);
    const url = await reserve('a.png', 3);
    expect(fetcher).toHaveBeenCalledTimes(1);
    await expect(send(url, new File(['abc'], 'a.png'))).rejects.toMatchObject({ status: 410 });
    expect(fetcher).toHaveBeenCalledTimes(2);
  });
});
it('sniffs raster bytes, ignoring editable metadata and rejecting active content', () => {
  expect(rasterType(new Uint8Array([137,80,78,71,13,10,26,10]))).toBe('image/png');
  expect(rasterType(new Uint8Array([255,216,255,224]))).toBe('image/jpeg');
  expect(rasterType(new TextEncoder().encode('RIFF1234WEBP'))).toBe('image/webp');
  expect(rasterType(new TextEncoder().encode('<svg onload="alert(1)">'))).toBeNull();
  expect(rasterType(new TextEncoder().encode('<html>'))).toBeNull();
});
