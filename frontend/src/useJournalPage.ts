import { useCallback, useEffect, useState } from "react";
import type { JournalPage } from "./api";
import { firstJournalPage, navigationForKey, nextJournalPage, previousJournalPage } from "./journalNavigation";

export function useJournalPage<T>(
  key: string,
  fetchPage: (cursor: string | null, signal: AbortSignal) => Promise<JournalPage<T>>,
) {
  const [history, setHistory] = useState(() => firstJournalPage(key));
  const navigation = navigationForKey(history, key);
  const cursor = navigation.cursors[navigation.index];
  const [revision, setRevision] = useState(0);
  const [result, setResult] = useState<{ key: string; page: JournalPage<T> } | null>(null);
  const [settledKey, setSettledKey] = useState<string | null>(null);
  const [fetching, setFetching] = useState(false);
  const [error, setError] = useState("");
  const requestKey = JSON.stringify([key, cursor, revision]);

  useEffect(() => {
    const controller = new AbortController();
    setFetching(true); setError("");
    void fetchPage(cursor, controller.signal).then((page) => {
      if (!controller.signal.aborted) setResult({ key: requestKey, page });
    }).catch((exc: unknown) => {
      if (!controller.signal.aborted) {
        setResult(null);
        setError(exc instanceof Error ? exc.message : "Не удалось загрузить журнал");
      }
    }).finally(() => {
      if (!controller.signal.aborted) { setFetching(false); setSettledKey(requestKey); }
    });
    return () => controller.abort();
  }, [cursor, fetchPage, requestKey]);

  const page = result?.key === requestKey ? result.page : null;
  const busy = fetching || settledKey !== requestKey;
  const load = useCallback(() => {
    setHistory(firstJournalPage(key));
    setRevision((value) => value + 1);
  }, [key]);

  return {
    items: page?.items ?? [], busy, error, setError, load,
    pageNumber: navigation.index + 1,
    canPrevious: navigation.index > 0 && !busy,
    canNext: Boolean(page?.has_more && page.next_cursor) && !busy,
    previous: () => setHistory(previousJournalPage(navigation)),
    next: () => { if (page?.next_cursor && !busy) setHistory(nextJournalPage(navigation, page.next_cursor)); },
  };
}
