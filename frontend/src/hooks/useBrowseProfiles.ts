import { useCallback, useEffect, useState } from "react";
import { getBrowseProfiles, type BrowseProfile } from "../api/browse";
import { useToast } from "../context/ToastContext";
import { DEFAULT_FILTERS, type BrowseFilters } from "../lib/browseFilters";

const PAGE_SIZE = 20;

interface Buffer {
    items: BrowseProfile[];
    cursor: number;
    direction: 1 | -1;
}

const EMPTY_BUFFER: Buffer = { items: [], cursor: 0, direction: 1 };

export function useBrowseProfiles(itemsPerScreen: number) {
    const [filters, setFilters] = useState<BrowseFilters>(DEFAULT_FILTERS);
    const [buffer, setBuffer] = useState<Buffer>(EMPTY_BUFFER);
    const [page, setPage] = useState(0);
    const [hasMore, setHasMore] = useState(true);
    const [isLoading, setIsLoading] = useState(false);
    const [error, setError] = useState<string | null>(null);
    const [attempt, setAttempt] = useState(0);
    const { showError } = useToast();

    const profiles = buffer.items;
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
                setBuffer((prev) => ({ ...prev, items: [...prev.items, ...batch] }));
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
        setBuffer(EMPTY_BUFFER);
        setHasMore(true);
        setPage(0);
    }, []);

    /** Drops a profile from the loaded pages (blocked), keeping the reader on the same spot. */
    const removeProfile = useCallback((userId: number) => {
        setBuffer((prev) => {
            const index = prev.items.findIndex((p) => p.id === userId);
            if (index === -1) return prev;
            return {
                ...prev,
                items: prev.items.filter((p) => p.id !== userId),
                cursor: index < prev.cursor ? prev.cursor - 1 : prev.cursor,
            };
        });
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
            const wouldExceedBuffer = prev.cursor + itemsPerScreen >= prev.items.length;
            if (wouldExceedBuffer && (isLoading || !hasMore)) return prev;
            return { ...prev, cursor: prev.cursor + itemsPerScreen, direction: 1 };
        });
    }

    const goBack = useCallback(() => {
        setBuffer((prev) => {
            if (prev.cursor === 0) return prev;
            return { ...prev, cursor: Math.max(0, prev.cursor - itemsPerScreen), direction: -1 };
        });
    }, [itemsPerScreen]);

    return {
        profiles,
        cursor: buffer.cursor,
        direction: buffer.direction,
        advance,
        goBack,
        hasMore,
        isLoading,
        error,
        atEnd,
        filters,
        applyFilters,
        removeProfile,
    };
}
