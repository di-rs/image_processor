import { test, expect, type Page } from '@playwright/test';
import type { ImageRecord } from '../../src/lib/types';
const states = ['pending_upload', 'uploading', 'uploaded', 'queued', 'processing', 'failed', 'finished'] as const;
const image = (id: number, status: ImageRecord['status'] = 'finished', parent: number | null = null): ImageRecord => ({
  id, filename: `sample-${id}.png`, content_type: 'image/png', original_url: `http://api:8000/images/${id}/original`, original_image: parent,
  generated_images: [], status, size_bytes: 68, width: 1, height: 1, created_at: '2026-10-03T12:00:00Z', updated_at: '2026-10-03T12:00:00Z',
  blob_key: `key-${id}`, upload_expires_at: null, 
});
const png = Buffer.from('iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+aX1sAAAAASUVORK5CYII=', 'base64');
async function backend(page: Page, opts: { offline?: boolean; uploadError?: boolean } = {}) {
  const calls: { method: string; path: string; body: string | null }[] = [];
  let edited = false;
  let deleted = false;
  await page.route('**/api/**', async route => {
    const req = route.request(); const url = new URL(req.url()); const path = url.pathname;
    calls.push({ method: req.method(), path: path + url.search, body: req.postData() });
    const json = (body: unknown, status = 200) => route.fulfill({ status, contentType: 'application/json', body: JSON.stringify(body) });
    if (opts.offline) return json({ detail: 'Backend unavailable' }, 502);
    if (path === '/api/health') return json({ status: 'ok' });
    if (path === '/api/') return json({ app: 'image_processor', version: 'demo-1.0', docs: '/docs', health: '/health' });
    if (path === '/api/debug/summary') return json({ counts: Object.fromEntries(states.map(s => [s, 1])), total: 7, queue_name: 'images' });
    if (path === '/api/images/uploads' && req.method() === 'POST') return opts.uploadError ? json({ detail: [{ loc: ['body', 'size_bytes'], msg: 'must be positive' }] }, 422) : json({ upload_url: 'http://api:8000/images/uploads/key' }, 201);
    if (path === '/api/images/uploads/key') return route.fulfill({ status: 204 });
    if (path === '/api/debug/images') {
      const status = url.searchParams.getAll('status');
      if (url.searchParams.get('order') === 'queue') {
        const items = states.filter(s => status.includes(s)).map(s => image(100 + states.indexOf(s), s));
        return json({ items, total: items.length, limit: 20, offset: 0 });
      }
      const offset = Number(url.searchParams.get('offset') ?? 0);
      const all = url.searchParams.get('kind') === 'all';
      const items = offset ? [image(30)] : status.includes('failed') ? [image(3, 'failed')] : all ? [...states.map((s, i) => image(i + 1, s)), image(8, 'finished', 1)] : [image(1), image(2)];
      const filtered = items.filter(i => !(deleted && i.id === 1)).map(i => edited && i.id === 1 ? { ...i, filename: 'renamed.png', content_type: 'text/html' } : i);
      return json({ items: filtered, total: deleted ? 20 : 21, limit: Number(url.searchParams.get('limit')), offset });
    }
    if (path.endsWith('/original')) return route.fulfill({ status: 200, contentType: 'application/octet-stream', body: png });
    if (/^\/api\/images\/\d+$/.test(path)) {
      const id = Number(path.split('/').pop());
      if (req.method() === 'PATCH') { edited = true; return json({ ...image(id), filename: 'renamed.png', content_type: 'text/html' }); }
      if (req.method() === 'DELETE') { deleted = true; return route.fulfill({ status: 204 }); }
      if (id === 2) return json({ detail: 'Generated lookup failed' }, 500);
      return json({ ...image(id), generated_images: id === 1 ? [image(11, 'finished', 1)] : [] });
    }
    return json({ detail: 'not found' }, 404);
  });
  return calls;
}

test('shows live DB states, independent generated lookup failures and pagination', async ({ page }) => {
  const calls = await backend(page);
  await page.goto('/');
  await expect(page.getByText('API reachable', { exact: true })).toBeVisible();
  await expect(page.getByText('demo-1.0')).toBeVisible();
  const live = page.getByRole('region', { name: 'Live queue' });
  for (const state of ['pending_upload', 'uploading', 'uploaded', 'queued', 'processing']) await expect(live.getByText(state, { exact: true })).toBeVisible();
  await expect(page.getByTestId('image-1').getByText('sample-11.png', { exact: true })).toBeVisible();
  await expect(page.getByTestId('image-2').getByText(/Generated lookup failed/)).toBeVisible();
  await page.getByTestId('image-2').getByRole('button', { name: 'Retry generated lookup' }).click();
  expect(calls.filter(c => c.path === '/api/images/2?include_generated=true').length).toBeGreaterThanOrEqual(2);
  await page.getByRole('button', { name: 'Next page' }).click();
  await expect(page.getByTestId('image-30')).toBeVisible();
  expect(calls.some(c => c.path.includes('offset=20'))).toBe(true);
  await page.getByRole('button', { name: 'Failed', exact: true }).click();
  await expect(page.getByTestId('image-3').getByText('Unsupported pixels', { exact: true })).toBeVisible();
  await page.getByRole('button', { name: 'All records', exact: true }).click();
  await expect(page.getByTestId('image-8').getByText('Generated from #1')).toBeVisible();
});

test('uploads files independently, exposes reservation/send and request inspector', async ({ page }) => {
  const calls = await backend(page);
  await page.goto('/');
  await page.getByLabel('Select files').setInputFiles([{ name: 'tiny.png', mimeType: 'image/png', buffer: png }, { name: 'second.png', mimeType: 'image/png', buffer: png }]);
  await page.getByRole('button', { name: 'Upload all' }).click();
  await expect(page.getByText('Sent · HTTP 204', { exact: true })).toHaveCount(2);
  expect(calls.filter(c => c.method === 'POST')).toHaveLength(2);
  expect(calls.filter(c => c.method === 'PUT')).toHaveLength(2);
  await page.getByLabel('Select files').setInputFiles({ name: 'manual.png', mimeType: 'image/png', buffer: png });
  const row = page.getByTestId('upload-row').last();
  await row.getByLabel('Declared filename').fill('manual-negative.png');
  await row.getByLabel('Declared size').fill('1');
  await row.getByRole('button', { name: 'Reserve only' }).click();
  await expect(row.getByText('Reserved · HTTP 201', { exact: true })).toBeVisible();
  expect(calls.filter(c => c.method === 'PUT')).toHaveLength(2);
  await row.getByRole('button', { name: 'Send bytes' }).click();
  await expect(row.getByText('Sent · HTTP 204', { exact: true })).toBeVisible();
  await page.getByText('Request inspector', { exact: true }).click();
  await expect(page.getByRole('region', { name: 'Request log' }).getByText('PUT', { exact: true })).toHaveCount(3);
});

test('reservation validation failure is explicit and does not send or auto retry', async ({ page }) => {
  const calls = await backend(page, { uploadError: true });
  await page.goto('/');
  await page.getByLabel('Select files').setInputFiles({ name: 'bad.png', mimeType: 'image/png', buffer: png });
  await page.getByRole('button', { name: 'Upload all' }).click();
  await expect(page.getByTestId('upload-row').getByText(/HTTP 422.*must be positive/)).toBeVisible();
  expect(calls.filter(c => c.method === 'POST')).toHaveLength(1);
  expect(calls.filter(c => c.method === 'PUT')).toHaveLength(0);
});

test('edits metadata, refreshes and confirms delete without claiming child cancellation', async ({ page }) => {
  const calls = await backend(page);
  await page.goto('/');
  const card = page.getByTestId('image-1');
  await card.getByText('Metadata & actions', { exact: true }).click();
  await card.getByLabel('Filename', { exact: true }).fill('renamed.png');
  await card.getByLabel('Content type').fill('text/html');
  await expect(card.getByLabel('Filename', { exact: true })).toHaveValue('renamed.png');
  await expect(card.getByLabel('Content type')).toHaveValue('text/html');
  await card.getByRole('button', { name: 'Save metadata' }).click();
  await expect(card.getByRole('heading', { name: 'renamed.png' })).toBeVisible();
  expect(calls.find(c => c.method === 'PATCH')?.body).toContain('text/html');
  await card.getByRole('button', { name: 'Delete record' }).click();
  await expect(card.getByText(/Children persist.*does not cancel/i)).toBeVisible();
  await card.getByRole('button', { name: 'Confirm delete' }).click();
  await expect(page.getByTestId('image-1')).toHaveCount(0);
});

test('refresh preserves dirty edits, syncs pristine fields and patches only edited metadata', async ({ page }) => {
  const calls = await backend(page);
  await page.goto('/');
  const card = page.getByTestId('image-1');
  await card.getByText('Metadata & actions', { exact: true }).click();
  await card.getByLabel('Filename', { exact: true }).fill('local-draft.png');
  await page.evaluate(() => fetch('/api/images/1', { method: 'PATCH', headers: { 'content-type': 'application/json' }, body: JSON.stringify({ content_type: 'text/html' }) }));
  await page.getByRole('button', { name: 'Refresh now' }).click();
  await expect(card.getByRole('heading', { name: 'renamed.png' })).toBeVisible();
  await expect(card.getByLabel('Filename', { exact: true })).toHaveValue('local-draft.png');
  await expect(card.getByLabel('Content type')).toHaveValue('text/html');
  await card.getByRole('button', { name: 'Save metadata' }).click();
  await expect(card.getByText('Metadata saved. Bytes are unchanged.', { exact: true })).toBeVisible();
  const patches = calls.filter(call => call.method === 'PATCH');
  expect(JSON.parse(patches[patches.length - 1].body ?? '{}')).toEqual({ filename: 'local-draft.png' });
});

test('accepts dropped files without uploading until explicitly requested', async ({ page }) => {
  const calls = await backend(page);
  await page.goto('/');
  const transfer = await page.evaluateHandle(() => { const data = new DataTransfer(); data.items.add(new File(['not pixels'], 'dropped.png', { type: 'image/png' })); return data; });
  await page.getByTestId('drop-zone').dispatchEvent('drop', { dataTransfer: transfer });
  await expect(page.getByTestId('upload-row').getByText('dropped.png', { exact: true })).toBeVisible();
  expect(calls.filter(c => c.method === 'POST')).toHaveLength(0);
});

test('manual uploads expose expired and reused URL errors without auto retry', async ({ page }) => {
  const calls = await backend(page);
  let sends = 0;
  await page.route('**/api/images/uploads/key', route => {
    sends++;
    return route.fulfill({ status: sends === 1 ? 410 : 409, contentType: 'application/json', body: JSON.stringify({ detail: sends === 1 ? 'Upload URL has expired' : 'Upload URL has already been used' }) });
  });
  await page.goto('/');
  await page.getByLabel('Select files').setInputFiles({ name: 'manual.png', mimeType: 'image/png', buffer: png });
  const row = page.getByTestId('upload-row');
  await row.getByRole('button', { name: 'Reserve only' }).click();
  await expect(row.getByText('Reserved · HTTP 201', { exact: true })).toBeVisible();
  await row.getByRole('button', { name: 'Send bytes' }).click();
  await expect(row.getByText(/HTTP 410.*expired/)).toBeVisible();
  expect(sends).toBe(1);
  await row.getByRole('button', { name: 'Send bytes' }).click();
  await expect(row.getByText(/HTTP 409.*already been used/)).toBeVisible();
  expect(sends).toBe(2);
  expect(calls.filter(c => c.method === 'POST')).toHaveLength(1);
});

test('an undecodable raster has a useful error instead of a broken image', async ({ page }) => {
  await backend(page);
  await page.route('**/api/images/1/original', route => route.fulfill({ status: 200, body: Buffer.from([137,80,78,71,13,10,26,10]), contentType: 'application/octet-stream' }));
  await page.goto('/');
  await expect(page.getByTestId('image-1').getByText('Browser could not decode these image bytes. Download to inspect.')).toBeVisible();
});

test('queue records can be expanded to inspect metadata and source bytes', async ({ page }) => {
  await backend(page);
  await page.goto('/');
  const queue = page.getByRole('region', { name: 'Live queue' });
  await queue.getByRole('button', { name: 'Inspect #104' }).first().click();
  await expect(queue.getByTestId('image-104')).toBeVisible();
});

test('offline is explicit and polling can be paused or refreshed manually', async ({ page }) => {
  await backend(page, { offline: true });
  await page.goto('/');
  await expect(page.getByText('API unreachable', { exact: true })).toBeVisible();
  await expect(page.getByRole('region', { name: 'Results' }).getByText(/Backend unavailable/)).toBeVisible();
  await page.getByRole('button', { name: 'Pause polling' }).click();
  await expect(page.getByRole('button', { name: 'Resume polling' })).toBeVisible();
  await page.getByRole('button', { name: 'Refresh now' }).click();
});
