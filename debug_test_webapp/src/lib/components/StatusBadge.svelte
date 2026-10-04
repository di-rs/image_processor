<script lang="ts">
  import type { Status } from '../types';
  let { status }: { status: Status } = $props();
</script>
<span class="badge {status}"><span class="dot"></span>{status}</span>
