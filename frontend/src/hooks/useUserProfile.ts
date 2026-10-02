import { useEffect, useState } from "react";
import { getUserProfile, type UserProfileDetail } from "../api/users";

export function useUserProfile(id: number) {
    const [profile, setProfile] = useState<UserProfileDetail | null>(null);
    const [isLoading, setIsLoading] = useState(true);
    const [error, setError] = useState<string | null>(null);

    useEffect(() => {
        let cancelled = false;
        setIsLoading(true);
        setError(null);

        getUserProfile(id)
            .then(async (response) => {
                if (!response.ok) {
                    const data = await response.json().catch(() => null);
                    throw new Error(data?.detail ?? "Could not load this profile.");
                }
                return response.json() as Promise<UserProfileDetail>;
            })
            .then((data) => {
                if (!cancelled) setProfile(data);
            })
            .catch((err) => {
                if (!cancelled) setError(err instanceof Error ? err.message : "Could not load this profile.");
            })
            .finally(() => {
                if (!cancelled) setIsLoading(false);
            });

        return () => {
            cancelled = true;
        };
    }, [id]);

    return { profile, isLoading, error };
}
