import { useCallback, useEffect, useState } from "react";

export function useProfileEntries<T>(fetcher: () => Promise<Response>) {
    const [entries, setEntries] = useState<T[]>([]);
    const [isLoading, setIsLoading] = useState(true);
    const [loadError, setLoadError] = useState(false);

    const load = useCallback(() => {
        setIsLoading(true);
        setLoadError(false);
        fetcher()
            .then(async (res) => {
                if (!res.ok) {
                    setLoadError(true);
                    return;
                }
                const data = await res.json();
                if (Array.isArray(data)) setEntries(data);
            })
            .catch(() => setLoadError(true))
            .finally(() => setIsLoading(false));
    }, [fetcher]);

    useEffect(() => {
        load();
    }, [load]);

    return { entries, isLoading, loadError, retry: load };
}
