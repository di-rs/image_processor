import { test, expect } from '@playwright/test';
import { createServer, type Server } from 'node:http';

let upstream: Server;
test.beforeAll(async () => {
  upstream = createServer(async (request, response) => {
    const chunks: Buffer[] = [];
    for await (const chunk of request) chunks.push(Buffer.from(chunk));
    if (request.url === '/') {
      response.setHeader('Content-Type', 'application/json');
      response.end(JSON.stringify({ app: 'integration-backend', version: 'test' }));
    } else if (request.url === '/images/uploads/stream') {
      response.setHeader('Content-Type', 'application/json');
      response.end(JSON.stringify({ bytes: Buffer.concat(chunks).length, cookie: request.headers.cookie ?? null }));
    } else if (request.url === '/images/2/original') {
      response.setHeader('Content-Type', 'application/octet-stream');
      response.setHeader('Content-Disposition', 'attachment; filename="test.png"');
      response.end(Buffer.from([0, 1, 2, 255]));
    } else {
      response.writeHead(410, { 'Content-Type': 'application/json' });
      response.end(JSON.stringify({ detail: 'Upload URL has expired' }));
    }
  });
  await new Promise<void>((resolve, reject) => {
    upstream.once('error', reject);
    upstream.listen(4187, '127.0.0.1', resolve);
  });
});
test.afterAll(async () => { await new Promise<void>((resolve, reject) => upstream.close(error => error ? reject(error) : resolve())); });

test('real SvelteKit route accepts metadata root without redirects', async ({ request }) => {
  const response = await request.get('/api/', { maxRedirects: 0 });
  expect(response.status()).toBe(200);
  expect(await response.json()).toEqual({ app: 'integration-backend', version: 'test' });
});

test('real proxy streams upload bytes and drops browser cookies', async ({ request }) => {
  const response = await request.put('/api/images/uploads/stream', {
    data: Buffer.alloc(1024 * 1024, 42),
    headers: { 'Content-Type': 'application/octet-stream', cookie: 'secret=not-forwarded' }
  });
  expect(response.status()).toBe(200);
  expect(await response.json()).toEqual({ bytes: 1024 * 1024, cookie: null });
});

test('real proxy preserves download bytes, safe headers and error details', async ({ request }) => {
  const download = await request.get('/api/images/2/original');
  expect(download.status()).toBe(200);
  expect(await download.body()).toEqual(Buffer.from([0, 1, 2, 255]));
  expect(download.headers()['content-disposition']).toContain('attachment');
  expect(download.headers()['x-content-type-options']).toBe('nosniff');
  const error = await request.put('/api/images/uploads/expired', { data: 'x' });
  expect(error.status()).toBe(410);
  expect(await error.json()).toEqual({ detail: 'Upload URL has expired' });
});

test('real proxy rejects unsupported endpoints', async ({ request }) => {
  expect((await request.get('/api/arbitrary-path')).status()).toBe(400);
});
