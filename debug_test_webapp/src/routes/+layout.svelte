<script lang="ts">
  import { QueryClient, QueryClientProvider } from '@tanstack/svelte-query';
  import type { Snippet } from 'svelte';
  import '../app.css';
  let { children }: { children: Snippet } = $props();
  const client = new QueryClient({ defaultOptions: {
    queries: { retry: false, staleTime: 1000, gcTime: 60000, refetchOnWindowFocus: false, refetchOnReconnect: false },
    mutations: { retry: false }
  } });
</script>
<QueryClientProvider {client}>{@render children()}</QueryClientProvider>
