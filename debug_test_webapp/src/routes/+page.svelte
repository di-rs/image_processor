<script lang="ts">
  import { onMount } from 'svelte';
  import { env } from '$env/dynamic/public';
  import { useQueryClient } from '@tanstack/svelte-query';
  import { ApiError } from '../lib/api';
  import { remote, paused, visible, lastRefresh } from '../lib/queries';
  import { statuses, type Summary } from '../lib/types';
  import StatusBadge from '../lib/components/StatusBadge.svelte';
  import UploadWorkbench from '../lib/components/UploadWorkbench.svelte';
  import LiveQueue from '../lib/components/LiveQueue.svelte';
  import Results from '../lib/components/Results.svelte';
  import RequestInspector from '../lib/components/RequestInspector.svelte';
  const health = remote<{ status: string }>('health', '/health', 3000);
  const meta = remote<{ app: string; version: string }>('meta', '/', 30000);
  const summary = remote<Summary>('summary', '/debug/summary', 3000);
  const client = useQueryClient();
  let refreshing = $state(false);
  async function refresh() { refreshing = true; try { await client.invalidateQueries(); } finally { refreshing = false; } }
  onMount(() => {
    const update = () => visible.set(!document.hidden);
    update(); document.addEventListener('visibilitychange', update);
    return () => document.removeEventListener('visibilitychange', update);
  });
</script>

<svelte:head><title>Image processor · Debug console</title><meta name="description" content="Local developer console for inspecting the image processing API, uploads, worker states and generated images." /></svelte:head>

<div class="app-shell">
  <header class="topbar"><a class="brand" href="/" aria-label="Image processor home"><span class="brand-mark">▧</span><span>IMAGE PROCESSOR<small>DEVELOPER CONSOLE</small></span></a><div class="top-links"><span class="local-label">LOCAL / NO AUTH</span><a href={env.PUBLIC_API_DOCS_URL ?? 'http://localhost:8000/docs'} target="_blank" rel="noreferrer">API docs ↗</a><a href={env.PUBLIC_RABBITMQ_URL ?? 'http://localhost:15672'} target="_blank" rel="noreferrer">RabbitMQ ↗</a></div></header>
  <main>
    <div class="hero"><div><span class="eyebrow">UPLOAD → QUEUE → PROCESS → INSPECT</span><h1>See the pipeline.<br /><span>Not just the result.</span></h1><p>Real requests. Real state. Originals and generated pixels, together.</p></div><div class="connection panel"><div class="connection-line"><span class="connection-dot" class:connected={$health.isSuccess && !$health.isError}></span><strong>{$health.isError ? 'API unreachable' : $health.isPending ? 'Connecting to API…' : 'API reachable'}</strong></div><div class="muted">Version <code>{$meta.data?.version ?? '—'}</code> · Queue <code>{$summary.data?.queue_name ?? '—'}</code></div><small>Last successful read: {$lastRefresh ? new Date($lastRefresh).toLocaleTimeString() : 'never'}</small><div class="actions"><button onclick={() => paused.update(value => !value)}>{$paused ? 'Resume polling' : 'Pause polling'}</button><button class="primary" onclick={refresh} disabled={refreshing}>{refreshing ? 'Refreshing…' : 'Refresh now'}</button></div><small>{$paused ? 'Polling paused. User actions still make requests.' : !$visible ? 'Background tab — interval polling paused.' : 'Live polling · mutations never automatically retried'}</small></div></div>
    {#if $summary.error instanceof ApiError && $summary.error.status === 404 && $health.isSuccess}
      <p class="callout warning" role="status">API reachable, but debug endpoints are disabled or unavailable. Check <code>DEBUG=true</code> and restart the backend after changing it. A 404 can also indicate a routing or backend-version mismatch; it does not prove DEBUG is disabled. Public upload actions remain available.</p>
    {/if}
    <p class="system-note"><span>ⓘ</span> API health only confirms the HTTP process responds — not database, broker or worker health. No worker heartbeat, exact broker positions or retry counters are recorded.</p>
    <section aria-label="State counts" class="state-strip">{#each statuses as state}<div class="state-cell"><StatusBadge status={state} /><strong>{$summary.data?.counts[state] ?? '—'}</strong></div>{/each}</section>
    <div class="summary-caption"><span>{$summary.data?.total ?? '—'} persisted records · counts include generated images</span>{#if $summary.error}<span class="error-text">Counts unavailable / stale: {$summary.error.message}</span>{:else}<span>PostgreSQL metadata + shared image volume</span>{/if}</div>
    <UploadWorkbench />
    <LiveQueue />
    <Results />
    <RequestInspector />
  </main>
  <footer><span>Debug surface, not an end-user app.</span><span>State persists in backend Docker volumes. Request history does not.</span></footer>
</div>
