import { useCallback, useEffect, useState } from "react";
import { getLikes, type Like } from "@/api/profile";

export function useProfileLikes() {
    const [likes, setLikes] = useState<Like[]>([]);
    const [isLoading, setIsLoading] = useState(true);
    const [loadError, setLoadError] = useState(false);

    const load = useCallback(() => {
        setIsLoading(true);
        setLoadError(false);
        getLikes()
            .then(async (res) => {
                if (!res.ok) {
                    setLoadError(true);
                    return;
                }
                const data = await res.json();
                if (Array.isArray(data)) setLikes(data);
            })
            .catch(() => setLoadError(true))
            .finally(() => setIsLoading(false));
    }, []);

    useEffect(() => {
        load();
    }, [load]);

    return { likes, isLoading, loadError, retry: load };
}
