import useSWR from "swr";
import { fetchActiveUsersData } from "@/lib/analytics/active";
import { buildActiveFallback } from "@/lib/analytics/constants";
import type { ActiveUsersRow } from "@/lib/analytics/types";

const ACTIVE_KEY = "active-users";

export function useActiveUsersData(cacheBuster: number) {
  const { data, error, isLoading, mutate } = useSWR<ActiveUsersRow[] | undefined, Error, [string, number]>(
    [ACTIVE_KEY, cacheBuster],
    ([, key]) => fetchActiveUsersData(key),
    {
      revalidateOnFocus: false,
      revalidateIfStale: false,
    },
  );

  const rows = data?.length ? data : error ? buildActiveFallback() : [];
  const usingFallback = Boolean(error && !data?.length);

  return { rows, error, isLoading, mutate, usingFallback };
}
