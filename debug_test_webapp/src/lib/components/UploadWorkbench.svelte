<script lang="ts">
  import { useQueryClient } from '@tanstack/svelte-query';
  import { reserve, send } from '../upload';
  const client = useQueryClient();
  type Row = { id: number; file: File; name: string; size: number; url: string; busy: boolean; attempted: boolean; message: string; error: string; ms: number | null };
  let rows: Row[] = $state([]);
  let sequence = 0;
  function select(event: Event) {
    const input = event.currentTarget as HTMLInputElement;
    addFiles(input.files ?? []);
    input.value = '';
  }
  function addFiles(files: Iterable<File>) {
    rows.push(...Array.from(files).map(file => ({ id: ++sequence, file, name: file.name, size: file.size, url: '', busy: false, attempted: false, message: 'Ready', error: '', ms: null })));
  }
  function drop(event: DragEvent) {
    event.preventDefault();
    addFiles(event.dataTransfer?.files ?? []);
  }
  async function run(row: Row, action: 'reserve' | 'send' | 'both') {
    row.busy = true; row.attempted = true; row.error = '';
    const start = performance.now();
    try {
      if (action !== 'send') {
        row.message = 'Reserving…';
        row.url = await reserve(row.name, Number(row.size));
        row.message = 'Reserved · HTTP 201';
        void client.invalidateQueries();
      }
      if (action !== 'reserve') {
        row.message = 'Sending bytes…';
        await send(row.url, row.file);
        row.message = 'Sent · HTTP 204';
      }
    } catch (error) { row.error = String(error); row.message = 'Request failed — not retried'; }
    finally { row.busy = false; row.ms = Math.round(performance.now() - start); void client.invalidateQueries(); }
  }
  function all() { for (const row of rows.filter(row => !row.attempted && !row.busy)) void run(row, 'both'); }
</script>
<section aria-label="Upload workbench" class="panel">
  <div class="section-heading"><div><span class="eyebrow">01 / INGEST</span><h2>Upload workbench</h2></div><span class="muted">POST reserve → PUT raw bytes</span></div>
  <div class="upload-toolbar"><label class="file-picker" data-testid="drop-zone" ondragover={(event) => event.preventDefault()} ondrop={drop}>Drop images or select files<input aria-label="Select files" type="file" multiple onchange={select} /></label><button class="primary" onclick={all} disabled={!rows.some(row => !row.attempted)}>Upload all</button><button onclick={() => rows = rows.filter(row => row.busy)} disabled={rows.some(row => row.busy)}>Clear files</button></div>
  <p class="muted">Each file is independent. Override declared metadata for negative tests, or reserve now and send later. No automatic retries; an uncertain failure may already have changed backend state.</p>
  {#each rows as row (row.id)}
    <div class="upload-row" data-testid="upload-row">
      <div><strong>{row.file.name}</strong><small>{row.file.size.toLocaleString()} actual bytes</small></div>
      <label>Declared filename<input aria-label="Declared filename" bind:value={row.name} disabled={row.busy} /></label>
      <label>Declared size<input aria-label="Declared size" type="number" bind:value={row.size} disabled={row.busy} /></label>
      <div class="actions"><button onclick={() => run(row, 'reserve')} disabled={row.busy}>Reserve only</button><button onclick={() => run(row, 'send')} disabled={row.busy || !row.url}>Send bytes</button></div>
      <div class="upload-result"><span aria-live="polite">{row.message}</span>{#if row.ms !== null}<span class="muted"> · {row.ms} ms</span>{/if}{#if row.url}<code>{row.url}</code>{/if}{#if row.error}<pre class="error">{row.error}</pre>{/if}</div>
    </div>
  {/each}
</section>
