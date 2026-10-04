<script lang="ts">
  import { derived, writable } from 'svelte/store';
  import { createQuery, type CreateQueryOptions } from '@tanstack/svelte-query';
  import { api } from '../api';
  import { paused, visible } from '../queries';
  import { statuses, type ImagePage, type Status } from '../types';
  import ImageCard from './ImageCard.svelte';
  type Tab = 'Finished' | 'Failed' | 'All records';
  const tabs: Tab[] = ['Finished', 'Failed', 'All records'];
  const filters = writable({ tab: 'Finished' as Tab, page: 0, size: 20, status: '' as Status | '', kind: 'all' });
  const results = createQuery(derived([filters, paused, visible], ([$filters, $paused, $visible]): CreateQueryOptions<ImagePage> => {
    const params = new URLSearchParams({ kind: $filters.tab === 'All records' ? $filters.kind : 'original', order: 'newest', limit: String($filters.size), offset: String($filters.page * $filters.size) });
    if ($filters.tab !== 'All records') params.set('status', $filters.tab === 'Finished' ? 'finished' : 'failed');
    else if ($filters.status) params.set('status', $filters.status);
    return { queryKey: ['results', params.toString()], queryFn: ({ signal }) => api<ImagePage>('/debug/images?' + params, { signal, polling: true }), refetchInterval: $paused || !$visible ? false : 5000 };
  }));
  function tab(value: Tab) { filters.update(f => ({ ...f, tab: value, page: 0 })); }
  $effect(() => {
    if ($results.data && $filters.page > 0 && $filters.page * $filters.size >= $results.data.total) filters.update(f => ({ ...f, page: Math.max(0, Math.ceil(($results.data?.total ?? 0) / f.size) - 1) }));
  });
</script>

<section aria-label="Results" class="results-section">
  <div class="section-heading"><div><span class="eyebrow">03 / INSPECT</span><h2>Image records</h2></div><span class="muted">Paginated on the backend · 5s polling</span></div>
  <div class="results-toolbar"><div class="tabs" aria-label="Result views">{#each tabs as value}<button class:active={$filters.tab === value} aria-pressed={$filters.tab === value} onclick={() => tab(value)}>{value}</button>{/each}</div><label class="inline-label">Per page<select aria-label="Results per page" bind:value={$filters.size} onchange={() => filters.update(f => ({ ...f, page: 0 }))}><option value={10}>10</option><option value={20}>20</option><option value={50}>50</option></select></label></div>
  {#if $filters.tab === 'All records'}<div class="filter-row"><label>State<select bind:value={$filters.status} onchange={() => filters.update(f => ({ ...f, page: 0 }))}><option value="">All states</option>{#each statuses as state}<option value={state}>{state}</option>{/each}</select></label><label>Relationship<select bind:value={$filters.kind} onchange={() => filters.update(f => ({ ...f, page: 0 }))}><option value="all">All records</option><option value="original">No parent reference</option><option value="generated">Generated / has parent</option></select></label></div>{/if}
  <p class="muted">{$filters.tab === 'All records' ? 'Includes generated images as independent records. A deleted parent clears child links, so no parent reference does not prove an image was uploaded.' : 'Originals / records without a parent reference. Each card independently fetches its linked outputs.'}</p>
  {#if $results.isPending}<div class="empty loading-state">Loading image records…</div>{/if}
  {#if $results.error}<div class="callout error"><p>{$results.error.message}</p><button onclick={() => $results.refetch()}>Retry results</button>{#if $results.data}<small>Showing stale data from the last successful request.</small>{/if}</div>{/if}
  {#if $results.data}
    {#if !$results.data.items.length}<div class="empty"><span class="empty-symbol">◇</span><h3>No matching records</h3><p>Upload an image above or choose another state.</p></div>{/if}
    <div class="image-grid">{#each $results.data.items as image (image.id)}<ImageCard {image} />{/each}</div>
    <nav class="pagination" aria-label="Results pagination"><span class="muted">{$results.data.total ? $filters.page * $filters.size + 1 : 0}–{Math.min(($filters.page + 1) * $filters.size, $results.data.total)} of {$results.data.total} records · Page {$filters.page + 1} / {Math.max(1, Math.ceil($results.data.total / $filters.size))}</span><div class="actions"><button onclick={() => filters.update(f => ({ ...f, page: f.page - 1 }))} disabled={$filters.page === 0 || $results.isFetching}>Previous page</button><button onclick={() => filters.update(f => ({ ...f, page: f.page + 1 }))} disabled={($filters.page + 1) * $filters.size >= $results.data.total || $results.isFetching}>Next page</button></div></nav>
  {/if}
</section>
