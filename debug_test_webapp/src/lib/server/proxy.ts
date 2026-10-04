import { allowedMethods } from '../paths';

type Fetcher = (input: string | URL | Request, init?: RequestInit) => Promise<Response>;
export async function proxy(request: Request, path: string, backend: string, fetcher: Fetcher = fetch, timeoutMs = 30000): Promise<Response> {
  const methods = allowedMethods(path);
  if (!methods) return Response.json({ detail: 'Invalid proxy path' }, { status: 400 });
  if (!methods.includes(request.method)) return Response.json({ detail: 'Method not allowed' }, { status: 405, headers: { allow: methods.join(', ') } });
  const controller = new AbortController();
  let timedOut = false;
  const timer = setTimeout(() => { timedOut = true; controller.abort(); }, timeoutMs);
  const cancel = () => controller.abort();
  request.signal.addEventListener('abort', cancel, { once: true });
  if (request.signal.aborted) cancel();
  const cleanup = () => { clearTimeout(timer); request.signal.removeEventListener('abort', cancel); };
  try {
    const base = new URL(backend);
    if (!['http:', 'https:'].includes(base.protocol) || base.username || base.password || base.pathname !== '/' || base.search || base.hash) throw new Error('Invalid backend origin');
    const target = new URL('/' + path, base);
    target.search = new URL(request.url).search;
    const headers = new Headers();
    for (const key of ['accept', 'content-type']) {
      const value = request.headers.get(key);
      if (value) headers.set(key, value);
    }
    const init: RequestInit & { duplex?: 'half' } = { method: request.method, headers, redirect: 'manual', signal: controller.signal };
    if (['POST', 'PUT', 'PATCH'].includes(request.method)) { init.body = request.body; init.duplex = 'half'; }
    const upstream = await fetcher(target, init);
    if (upstream.status >= 300 && upstream.status < 400) {
      await upstream.body?.cancel(); cleanup();
      return Response.json({ detail: 'Upstream redirects are blocked' }, { status: 502 });
    }
    const responseHeaders = new Headers({ 'cache-control': 'no-store', 'x-content-type-options': 'nosniff' });
    for (const key of ['content-type', 'content-disposition']) {
      const value = upstream.headers.get(key);
      if (value) responseHeaders.set(key, value);
    }
    if (!upstream.body) { cleanup(); return new Response(null, { status: upstream.status, headers: responseHeaders }); }
    const reader = upstream.body.getReader();
    const body = new ReadableStream<Uint8Array>({
      async pull(stream) {
        try {
          const { done, value } = await reader.read();
          if (done) { cleanup(); stream.close(); } else stream.enqueue(value);
        } catch (error) { cleanup(); stream.error(error); }
      },
      async cancel(reason) { controller.abort(); cleanup(); await reader.cancel(reason); }
    });
    return new Response(body, { status: upstream.status, headers: responseHeaders });
  } catch {
    cleanup();
    return Response.json({ detail: timedOut ? 'Backend request timed out' : 'Backend unavailable' }, { status: timedOut ? 504 : 502 });
  }
}
