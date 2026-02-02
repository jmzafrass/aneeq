import useSWR from "swr";
import { buildRetentionFallback } from "@/lib/analytics/constants";
import { fetchRetentionData } from "@/lib/analytics/retention";
import type { RetentionRow } from "@/lib/analytics/types";

const RETENTION_KEY = "retention";

export function useRetentionData(cacheBuster: number) {
  const { data, error, isLoading, mutate } = useSWR<RetentionRow[] | undefined, Error, [string, number]>(
    [RETENTION_KEY, cacheBuster],
    ([, key]) => fetchRetentionData(key),
    {
      revalidateOnFocus: false,
      revalidateIfStale: false,
    },
  );

  const rows = data?.length ? data : error ? buildRetentionFallback() : [];
  const usingFallback = Boolean(error && !data?.length);

  return {
    rows,
    error,
    isLoading,
    mutate,
    usingFallback,
  };
}
