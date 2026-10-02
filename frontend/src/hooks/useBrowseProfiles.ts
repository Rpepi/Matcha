import { useCallback, useEffect, useState } from "react";
import { getBrowseProfiles, type BrowseProfile } from "../api/browse";
import { useToast } from "../context/ToastContext";
import { DEFAULT_FILTERS, type BrowseFilters } from "../lib/browseFilters";

const PAGE_SIZE = 20;

interface Buffer {
    old: BrowseProfile[];
    new: BrowseProfile[];
    cursor: number;
}

export function useBrowseProfiles(itemsPerScreen: number) {
    const [filters, setFilters] = useState<BrowseFilters>(DEFAULT_FILTERS);
    const [buffer, setBuffer] = useState<Buffer>({ old: [], new: [], cursor: 0 });
    const [page, setPage] = useState(0);
    const [hasMore, setHasMore] = useState(true);
    const [isLoading, setIsLoading] = useState(false);
    const [error, setError] = useState<string | null>(null);
    const [attempt, setAttempt] = useState(0);
    const { showError } = useToast();

    const profiles = [...buffer.old, ...buffer.new];
    const atEnd = !hasMore && buffer.cursor + itemsPerScreen >= profiles.length;

    useEffect(() => {
        let cancelled = false;
        setIsLoading(true);
        setError(null);

        getBrowseProfiles(page, filters)
            .then(async (response) => {
                if (!response.ok) {
                    const data = await response.json().catch(() => null);
                    throw new Error(data?.detail ?? "Could not load profiles. Please try again.");
                }
                return response.json() as Promise<BrowseProfile[]>;
            })
            .then((batch) => {
                if (cancelled) return;
                setBuffer((prev) => {
                    const evicted = prev.old.length > 0;
                    return {
                        old: prev.new,
                        new: batch,
                        cursor: evicted ? Math.max(0, prev.cursor - PAGE_SIZE) : prev.cursor,
                    };
                });
                setHasMore(batch.length === PAGE_SIZE);
            })
            .catch((err) => {
                if (cancelled) return;
                const message = err instanceof Error ? err.message : "Could not load profiles. Please try again.";
                setError(message);
                showError(message);
            })
            .finally(() => {
                if (!cancelled) setIsLoading(false);
            });

        return () => {
            cancelled = true;
        };
    }, [page, filters, attempt, showError]);

    const applyFilters = useCallback((next: BrowseFilters) => {
        setFilters(next);
        setBuffer({ old: [], new: [], cursor: 0 });
        setHasMore(true);
        setPage(0);
    }, []);

    const loadMore = useCallback(() => {
        if (hasMore && !isLoading) setPage((p) => p + 1);
    }, [hasMore, isLoading]);

    useEffect(() => {
        if (profiles.length > 0 && !isLoading && !error && hasMore && buffer.cursor + itemsPerScreen >= profiles.length) {
            loadMore();
        }
    }, [profiles.length, buffer.cursor, itemsPerScreen, hasMore, isLoading, error, loadMore]);

    function advance() {
        if (error && buffer.cursor + itemsPerScreen >= profiles.length) {
            setAttempt((a) => a + 1);
            return;
        }
        setBuffer((prev) => {
            const bufferedCount = prev.old.length + prev.new.length;
            const wouldExceedBuffer = prev.cursor + itemsPerScreen >= bufferedCount;
            if (wouldExceedBuffer && (isLoading || !hasMore)) return prev;
            return { ...prev, cursor: prev.cursor + itemsPerScreen };
        });
    }

    return {
        profiles,
        cursor: buffer.cursor,
        advance,
        hasMore,
        isLoading,
        error,
        atEnd,
        filters,
        applyFilters,
    };
}
