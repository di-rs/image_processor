import { derived, writable } from 'svelte/store';
import { createQuery, type CreateQueryOptions } from '@tanstack/svelte-query';
import { api } from './api';
export const paused = writable(false);
export const visible = writable(true);
export const lastRefresh = writable<number | null>(null);
export function remote<T>(key: string, path: string, interval: number) {
  return createQuery<T>(derived([paused, visible], ([$paused, $visible]): CreateQueryOptions<T> => ({
    queryKey: [key, path],
    queryFn: async ({ signal }) => {
      const data = await api<T>(path, { signal, polling: true });
      lastRefresh.set(Date.now());
      return data;
    },
    refetchInterval: $paused || !$visible ? false : interval,
    refetchIntervalInBackground: false
  })));
}
