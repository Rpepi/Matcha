import { useCallback, useEffect, useState } from "react";
import { getVisits, type Visit } from "@/api/profile";

export function useProfileVisits() {
    const [visits, setVisits] = useState<Visit[]>([]);
    const [isLoading, setIsLoading] = useState(true);
    const [loadError, setLoadError] = useState(false);

    const load = useCallback(() => {
        setIsLoading(true);
        setLoadError(false);
        getVisits()
            .then(async (res) => {
                if (!res.ok) {
                    setLoadError(true);
                    return;
                }
                const data = await res.json();
                if (Array.isArray(data)) setVisits(data);
            })
            .catch(() => setLoadError(true))
            .finally(() => setIsLoading(false));
    }, []);

    useEffect(() => {
        load();
    }, [load]);

    return { visits, isLoading, loadError, retry: load };
}
