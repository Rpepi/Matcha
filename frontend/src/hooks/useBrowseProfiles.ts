import { useEffect, useState } from "react";
import { getBrowseProfiles, type BrowseProfile } from "../api/browse";

const PAGE_SIZE = 20;

interface Buffer {
    old: BrowseProfile[];
    new: BrowseProfile[];
    cursor: number;
}

export function useBrowseProfiles() {
    const [buffer, setBuffer] = useState<Buffer>({ old: [], new: [], cursor: 0 });
    const [page, setPage] = useState(0);
    const [hasMore, setHasMore] = useState(true);
    const [isLoading, setIsLoading] = useState(false);
    const [error, setError] = useState<string | null>(null);

    useEffect(() => {
        let cancelled = false;
        setIsLoading(true);
        setError(null);

        getBrowseProfiles(page)
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
                if (!cancelled) setError(err instanceof Error ? err.message : "Could not load profiles. Please try again.");
            })
            .finally(() => {
                if (!cancelled) setIsLoading(false);
            });

        return () => {
            cancelled = true;
        };
    }, [page]);

    function loadMore() {
        if (hasMore && !isLoading) setPage((p) => p + 1);
    }

    function advance(itemsPerScreen: number) {
        setBuffer((prev) => ({ ...prev, cursor: prev.cursor + itemsPerScreen }));
    }

    return {
        profiles: [...buffer.old, ...buffer.new],
        cursor: buffer.cursor,
        advance,
        hasMore,
        isLoading,
        error,
        loadMore,
    };
}
