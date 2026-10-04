<script lang="ts">
  import { requestLog, clearRequests } from '../requests';
  let showPolling = $state(false);
  const entries = $derived($requestLog.filter(entry => showPolling || !entry.polling));
</script>

<details class="panel inspector">
  <summary><span class="eyebrow">04 / WIRE</span> <strong>Request inspector</strong><span class="muted">{$requestLog.length} / 100 retained</span></summary>
  <section aria-label="Request log">
    <div class="inspector-toolbar"><label class="check"><input type="checkbox" bind:checked={showPolling} /> Include polling & preview requests</label><button onclick={clearRequests}>Clear log</button></div>
    <p class="muted">Session-only, newest first. Binary bodies omitted; text truncated to 4 KiB. Inspect your browser Network tab for complete transfers. Downloads opened directly are not logged here.</p>
    {#if !entries.length}<p class="empty">No matching requests yet. Upload or edit an image, or include background reads.</p>{/if}
    {#each entries as entry (entry.id)}
      <details class="request-entry">
        <summary><code class="method">{entry.method}</code><code class="request-path">{entry.path}</code><span class:error-text={entry.status === null || entry.status >= 400}>{entry.status ?? 'NETWORK'}</span><span class="muted">{entry.ms} ms</span></summary>
        <small>{entry.at}{entry.polling ? ' · background read' : ''}</small>
        <div class="request-bodies"><div><h4>Request</h4><pre>{entry.request}</pre></div><div><h4>Response</h4><pre>{entry.response}</pre></div></div>
      </details>
    {/each}
  </section>
</details>
