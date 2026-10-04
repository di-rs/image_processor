<script lang="ts">
  import { remote } from '../queries';
  import type { ImagePage } from '../types';
  import StatusBadge from './StatusBadge.svelte';
  import ImageCard from './ImageCard.svelte';
  let expanded = $state<number | null>(null);
  const active = remote<ImagePage>('queue', '/debug/images?status=processing&status=queued&kind=all&order=queue&limit=20&offset=0', 2000);
  const waiting = remote<ImagePage>('awaiting', '/debug/images?status=pending_upload&status=uploading&status=uploaded&kind=all&order=queue&limit=20&offset=0', 2000);
  function age(value: string) { const seconds = Math.max(0, Math.floor((Date.now() - Date.parse(value)) / 1000)); return seconds < 60 ? `${seconds}s` : seconds < 3600 ? `${Math.floor(seconds / 60)}m` : `${Math.floor(seconds / 3600)}h`; }
</script>
<section aria-label="Live queue" class="panel">
  <div class="section-heading"><div><span class="eyebrow">02 / OBSERVE</span><h2>Live queue</h2></div><span class="muted">2s polling</span></div>
  <p class="muted">Database state, not broker positions. Processing first, queued oldest first. Age is since creation — not processing duration or historical trace.</p>
  {#each [{ title: 'Processing & queued', query: $active }, { title: 'Awaiting upload / publication', query: $waiting }] as group}
    <div class="subheading"><h3>{group.title}</h3><span class="muted">{group.query.data?.items.length ?? 0} shown / {group.query.data?.total ?? '—'} total · bounded to 20</span></div>
    {#if group.query.isPending}<p class="muted">Loading database state…</p>{/if}
    {#if group.query.error}<p class="error">{group.query.error.message}{group.query.data ? ' · Showing stale data.' : ''}</p>{/if}
    {#if group.query.data}
      {#if group.query.data.items.length === 0}<p class="empty">No records in these states.</p>{/if}
      <div class="table-scroll"><table><thead><tr><th>Record</th><th>Filename</th><th>State</th><th>Age</th><th>Updated</th><th>Inspect</th></tr></thead><tbody>
        {#each group.query.data.items as image (image.id)}<tr><td class="mono">#{image.id}</td><td>{image.filename}<small>{image.original_image !== null ? `Generated from #${image.original_image}` : 'No parent reference'}</small></td><td><StatusBadge status={image.status} /></td><td title={image.created_at}>{age(image.created_at)}</td><td class="muted">{new Date(image.updated_at).toLocaleTimeString()}{#if image.upload_expires_at}<small>Upload expires: {new Date(image.upload_expires_at).toLocaleTimeString()}</small>{/if}</td><td><button aria-label={`Inspect #${image.id}`} aria-expanded={expanded === image.id} onclick={() => expanded = expanded === image.id ? null : image.id}>{expanded === image.id ? 'Close' : 'Inspect'}</button></td></tr>{#if expanded === image.id}<tr><td colspan="6"><ImageCard {image} /></td></tr>{/if}{/each}
      </tbody></table></div>
    {/if}
  {/each}
</section>
