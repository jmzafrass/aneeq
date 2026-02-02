import useSWR from "swr";
import { buildLtvFallback } from "@/lib/analytics/constants";
import { fetchLtvData } from "@/lib/analytics/ltv";
import type { LtvRow } from "@/lib/analytics/types";

const LTV_KEY = "ltv";

export function useLtvData(cacheBuster: number) {
  const { data, error, isLoading, mutate } = useSWR<LtvRow[] | undefined, Error, [string, number]>(
    [LTV_KEY, cacheBuster],
    ([, key]) => fetchLtvData(key),
    {
      revalidateOnFocus: false,
      revalidateIfStale: false,
    },
  );

  const rows = data?.length ? data : error ? buildLtvFallback() : [];
  const usingFallback = Boolean(error && !data?.length);

  return {
    rows,
    error,
    isLoading,
    mutate,
    usingFallback,
  };
}
