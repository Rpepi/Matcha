import { useCallback, useEffect, useState } from "react";
import { getBrowseProfiles, type BrowseProfile } from "../api/browse";

const PAGE_SIZE = 20;

interface Buffer {
    old: BrowseProfile[];
    new: BrowseProfile[];
    cursor: number;
}

export function useBrowseProfiles(itemsPerScreen: number) {
    const [buffer, setBuffer] = useState<Buffer>({ old: [], new: [], cursor: 0 });
    const [page, setPage] = useState(0);
    const [hasMore, setHasMore] = useState(true);
    const [isLoading, setIsLoading] = useState(false);
    const [error, setError] = useState<string | null>(null);

    const profiles = [...buffer.old, ...buffer.new];

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

    const loadMore = useCallback(() => {
        if (hasMore && !isLoading) setPage((p) => p + 1);
    }, [hasMore, isLoading]);

    useEffect(() => {
        if (profiles.length > 0 && !isLoading && hasMore && buffer.cursor + itemsPerScreen >= profiles.length) {
            loadMore();
        }
    }, [profiles.length, buffer.cursor, itemsPerScreen, hasMore, isLoading, loadMore]);

    function advance() {
        setBuffer((prev) => ({ ...prev, cursor: prev.cursor + itemsPerScreen }));
    }

    return {
        profiles,
        cursor: buffer.cursor,
        advance,
        hasMore,
        isLoading,
        error,
    };
}
