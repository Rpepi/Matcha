import { useCallback, useEffect, useState } from "react";
import { useToast } from "@/context/ToastContext";
import { getBlockedUsers, unblockUser, type BlockedUser } from "@/api/block";

export function useProfileBlockedUsers() {
    const { showError } = useToast();
    const [blockedUsers, setBlockedUsers] = useState<BlockedUser[]>([]);
    const [isLoading, setIsLoading] = useState(true);
    const [loadError, setLoadError] = useState(false);
    const [isExpanded, setIsExpanded] = useState(false);
    const [unblockingId, setUnblockingId] = useState<number | null>(null);

    useEffect(() => {
        getBlockedUsers()
            .then(async (res) => {
                if (!res.ok) {
                    setLoadError(true);
                    return;
                }
                const data = await res.json();
                if (Array.isArray(data)) setBlockedUsers(data);
            })
            .catch(() => setLoadError(true))
            .finally(() => setIsLoading(false));
    }, []);

    const toggleExpanded = useCallback(() => setIsExpanded((v) => !v), []);

    const unblock = useCallback(
        async (id: number) => {
            setUnblockingId(id);
            try {
                const response = await unblockUser(id);
                if (!response.ok) {
                    const data = await response.json().catch(() => null);
                    showError(data?.detail ?? "Could not unblock this user. Please try again.");
                    return;
                }
                setBlockedUsers((prev) => prev.filter((u) => u.id !== id));
            } catch {
                showError("Could not unblock this user. Please check your connection and try again.");
            } finally {
                setUnblockingId(null);
            }
        },
        [showError],
    );

    return { blockedUsers, isLoading, loadError, isExpanded, toggleExpanded, unblockingId, unblock };
}
