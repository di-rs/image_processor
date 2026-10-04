<script lang="ts">
  import { api } from '../api';
  import { rasterType } from '../preview';
  let { id, filename, revision }: { id: number; filename: string; revision: string } = $props();
  let src = $state('');
  let error = $state('');
  let loading = $state(true);
  let attempt = $state(0);
  $effect(() => {
    const path = `/images/${id}/original`;
    void revision; void attempt;
    const controller = new AbortController();
    let objectUrl = '';
    src = ''; error = ''; loading = true;
    void (async () => {
      try {
        const blob = await api<Blob>(path, { binary: true, signal: controller.signal, polling: true });
        if (blob.size > 20 * 1024 * 1024) throw new Error('Preview limited to 20 MiB; use download.');
        const type = rasterType(new Uint8Array(await blob.slice(0, 16).arrayBuffer()));
        if (!type) throw new Error('Preview blocked: only byte-verified PNG, JPEG or WebP. Use download.');
        if (controller.signal.aborted) return;
        objectUrl = URL.createObjectURL(new Blob([blob], { type }));
        src = objectUrl;
      } catch (cause) { if (!controller.signal.aborted) error = String(cause); }
      finally { if (!controller.signal.aborted) loading = false; }
    })();
    return () => { controller.abort(); if (objectUrl) URL.revokeObjectURL(objectUrl); };
  });
</script>
<div class="preview">
  {#if loading}<span class="muted">Fetching raster…</span>{:else if error}<div><p class="error">{error}</p><button onclick={() => attempt++}>Retry preview</button></div>{:else}<img {src} alt={filename} loading="lazy" onerror={() => error = 'Browser could not decode these image bytes. Download to inspect.'} />{/if}
</div>
