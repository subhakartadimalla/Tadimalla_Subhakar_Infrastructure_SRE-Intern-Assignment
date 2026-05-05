import { useCallback, useEffect, useState } from "react";

function normalizeError(e) {
  const detail = e?.detail ?? e?.message ?? "Request failed";
  if (typeof detail === "string") return detail;
  try {
    return JSON.stringify(detail);
  } catch {
    return String(detail);
  }
}

export function useFetch(fetcher, deps = []) {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  const run = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const d = await fetcher();
      setData(d);
      return d;
    } catch (e) {
      setError(normalizeError(e));
      return null;
    } finally {
      setLoading(false);
    }
  }, deps);

  useEffect(() => {
    void run();
  }, [run]);

  return { data, loading, error, refetch: run };
}

