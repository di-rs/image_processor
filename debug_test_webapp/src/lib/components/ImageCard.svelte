<script lang="ts">
  import { untrack } from 'svelte';
  import { derived, writable } from 'svelte/store';
  import { createMutation, createQuery, useQueryClient, type CreateQueryOptions } from '@tanstack/svelte-query';
  import { api, jsonBody } from '../api';
  import { paused, visible } from '../queries';
  import type { ImageRecord } from '../types';
  import ImagePreview from './ImagePreview.svelte';

  import StatusBadge from './StatusBadge.svelte';

  let { image }: { image: ImageRecord } = $props();
  const id = untrack(() => image.id);
  const client = useQueryClient();
  const hasParent = writable(untrack(() => image.original_image !== null));
  $effect(() => hasParent.set(image.original_image !== null));
  const generated = createQuery(derived([paused, visible, hasParent], ([$paused, $visible, $hasParent]): CreateQueryOptions<ImageRecord> => ({
    queryKey: ['generated', id],
    queryFn: ({ signal }) => api<ImageRecord>(`/images/${id}?include_generated=true`, { signal, polling: true }),
    enabled: !$hasParent,
    refetchInterval: $paused || !$visible ? false : 5000
  })));
  let opened = $state(false);
  let filename = $state(untrack(() => image.filename));
  let contentType = $state(untrack(() => image.content_type));
  let filenameDirty = $state(false);
  let contentTypeDirty = $state(false);
  $effect(() => {
    if (!filenameDirty) filename = image.filename;
    if (!contentTypeDirty) contentType = image.content_type;
  });
  let confirming = $state(false);
  let actionMessage = $state('');
  let copied = $state(false);
  const inspect = writable(false);
  const details = createQuery(derived(inspect, ($inspect): CreateQueryOptions<ImageRecord> => ({
    queryKey: ['debug-detail', id], enabled: $inspect,
    queryFn: ({ signal }) => api<ImageRecord>(`/debug/images/${id}`, { signal })
  })));
  $effect(() => inspect.set(opened));
  const mutation = createMutation({
    mutationFn: async (action: 'save' | 'delete') => {
      if (action === 'save') {
        const patch = {
          ...(filenameDirty ? { filename } : {}),
          ...(contentTypeDirty ? { content_type: contentType } : {})
        };
        return api(`/images/${id}`, { method: 'PATCH', ...jsonBody(patch) });
      }
      return api(`/images/${id}`, { method: 'DELETE' });
    },
    onSuccess: async (_data, action) => {
      actionMessage = action === 'save' ? 'Metadata saved. Bytes are unchanged.' : 'Record deleted.';
      confirming = false;
      await client.invalidateQueries();
      if (action === 'save') { filenameDirty = false; contentTypeDirty = false; }
    },
    onError: () => { actionMessage = ''; }
  });
  function openDetails(event: Event) {
    opened = (event.currentTarget as HTMLDetailsElement).open;

  }
  async function copyId() {
    try { await navigator.clipboard.writeText(String(id)); copied = true; }
    catch { actionMessage = `Clipboard unavailable. Image ID: ${id}`; }
  }
  const children = $derived($generated.data?.generated_images ?? []);
</script>

<article class="image-card" data-testid={`image-${id}`}>
  <header class="card-heading"><div class="card-title"><span class="mono muted">#{id}</span><h3>{image.filename}</h3></div><StatusBadge status={image.status} /></header>
  <div class="card-subtitle"><span>{image.original_image !== null ? `Generated from #${image.original_image}` : 'Original / no parent reference'}</span><span>{image.width ?? '—'} × {image.height ?? '—'} px · {image.size_bytes.toLocaleString()} bytes</span></div>
  <div class="comparison">
    <figure><figcaption><span>{image.original_image !== null ? 'GENERATED RECORD' : 'SOURCE'}</span><code>#{id}</code></figcaption>
      {#if image.original_url}<ImagePreview {id} filename={image.filename} revision={image.updated_at} />{:else}<div class="preview"><span class="muted">Bytes not available in this state</span></div>{/if}
      {#if image.original_url}<a class="download" href={`/api/images/${id}/original`} download>↓ Download stored bytes</a>{/if}
    </figure>
    {#if image.original_image === null}
      <div class="generated-pane">
        <div class="generated-label"><span>GENERATED OUTPUT</span><code>GET /images/{id}?include_generated=true</code></div>
        {#if $generated.isPending}<div class="preview"><span class="muted">Fetching linked images…</span></div>{/if}
        {#if $generated.error}<div class="callout error"><p>{$generated.error.message}</p><button onclick={() => $generated.refetch()} disabled={$generated.isFetching}>Retry generated lookup</button>{#if $generated.data}<small>Showing last successful result below.</small>{/if}</div>{/if}
        {#if $generated.data && !children.length}<div class="preview"><span class="muted">{image.status === 'finished' ? 'No linked generated images returned.' : 'No output yet — see processing state.'}</span></div>{/if}
        {#each children as child (child.id)}
          <figure><figcaption><span>{child.filename}</span><code>#{child.id}</code></figcaption>
            {#if child.original_url}<ImagePreview id={child.id} filename={child.filename} revision={child.updated_at} />{:else}<div class="preview"><span class="muted">Generated bytes unavailable</span></div>{/if}
            <div class="child-caption"><span>{child.width ?? '—'} × {child.height ?? '—'} · {child.size_bytes.toLocaleString()} bytes</span><StatusBadge status={child.status} /></div>
            {#if child.original_url}<a class="download" href={`/api/images/${child.id}/original`} download>↓ Download generated bytes</a>{/if}
            <details class="child-details"><summary>Generated metadata</summary><pre>{JSON.stringify(child, null, 2)}</pre></details>
          </figure>
        {/each}
        <small class="muted">Separate request per original · API returns at most 20 linked images.</small>
      </div>
    {/if}
  </div>
  {#if image.status === 'failed'}<div class="callout error"><strong>Processing failed</strong><p>PostgreSQL reports a failure. Inspect processing logs separately in Loki.</p><small>No automatic retry for non-database failures. Upload again to create a new job.</small></div>{/if}

  <details class="metadata" ontoggle={openDetails}>
    <summary>Metadata & actions</summary>
    <dl class="metadata-grid"><dt>Created</dt><dd>{image.created_at}</dd><dt>Updated</dt><dd>{image.updated_at}</dd><dt>Content type</dt><dd>{image.content_type}</dd><dt>Storage key</dt><dd>{image.blob_key ?? '—'}</dd><dt>Upload expiry</dt><dd>{image.upload_expires_at ?? 'Not applicable / no longer reserved'}</dd></dl>
    {#if image.upload_expires_at}<p class="callout">Reservation {Date.parse(image.upload_expires_at) < Date.now() ? 'has expired' : 'expires'} at {image.upload_expires_at}. Expiration is not a separate backend state.</p>{/if}
    <form onsubmit={(event) => { event.preventDefault(); $mutation.mutate('save'); }}>
      <div class="form-grid"><label>Filename<input required maxlength="255" bind:value={filename} oninput={() => filenameDirty = true} disabled={$mutation.isPending} /></label><label>Content type<input required maxlength="127" bind:value={contentType} oninput={() => contentTypeDirty = true} disabled={$mutation.isPending} /></label></div>
      <div class="actions"><button type="submit" disabled={$mutation.isPending || (!filenameDirty && !contentTypeDirty)}>Save metadata</button><button type="button" onclick={copyId}>{copied ? 'Copied ID' : 'Copy ID'}</button><button class="danger" type="button" onclick={() => confirming = true} disabled={$mutation.isPending}>Delete record</button></div>
    </form>
    {#if confirming}<div class="callout warning"><p>Delete #{id} and its stored bytes? Children persist. This does not cancel a running worker or broker message.</p><div class="actions"><button class="danger" onclick={() => $mutation.mutate('delete')} disabled={$mutation.isPending}>Confirm delete</button><button onclick={() => confirming = false}>Keep record</button></div></div>{/if}
    {#if $mutation.error}<p class="error" role="alert">{$mutation.error.message} — not retried automatically.</p>{/if}
    {#if actionMessage}<p class="success" role="status">{actionMessage}</p>{/if}
    <details><summary>Raw debug response <code>GET /debug/images/{id}</code></summary>{#if $details.error}<p class="error">{$details.error.message}</p><button onclick={() => $details.refetch()}>Retry debug details</button>{/if}<pre>{JSON.stringify($details.data ?? image, null, 2)}</pre></details>
  </details>
</article>
