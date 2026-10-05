import { useCallback, useEffect, useState } from "react";
import { useToast } from "@/context/ToastContext";
import { getBlockedUsers, unblockUser, type BlockedUser } from "@/api/block";

export function useProfileBlockedUsers() {
    const { showError } = useToast();
    const [blockedUsers, setBlockedUsers] = useState<BlockedUser[]>([]);
    const [isLoading, setIsLoading] = useState(true);
    const [isExpanded, setIsExpanded] = useState(false);
    const [unblockingId, setUnblockingId] = useState<number | null>(null);

    useEffect(() => {
        getBlockedUsers()
            .then(async (res) => {
                if (!res.ok) return;
                const data = await res.json();
                if (Array.isArray(data)) setBlockedUsers(data);
            })
            .finally(() => setIsLoading(false));
    }, []);

    const toggleExpanded = useCallback(() => setIsExpanded((v) => !v), []);

    const unblock = useCallback(
        async (id: number) => {
            setUnblockingId(id);
            const response = await unblockUser(id);
            setUnblockingId(null);
            if (!response.ok) {
                const data = await response.json().catch(() => null);
                showError(data?.detail ?? "Could not unblock this user. Please try again.");
                return;
            }
            setBlockedUsers((prev) => prev.filter((u) => u.id !== id));
        },
        [showError],
    );

    return { blockedUsers, isLoading, isExpanded, toggleExpanded, unblockingId, unblock };
}
