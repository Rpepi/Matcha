import { useCallback } from "react";
import { logout } from "@/api/auth";
import { useProfileContext } from "@/context/ProfileContext";
import { useToast } from "@/context/ToastContext";

/** One click logs out from anywhere: the session is dropped, then the route guards send the visitor to /login. */
export function useLogout() {
    const { refetch } = useProfileContext();
    const { showError } = useToast();

    return useCallback(async () => {
        try {
            const response = await logout();
            if (!response.ok) {
                showError("Could not log out. Please try again.");
                return;
            }
            await refetch();
        } catch {
            showError("Could not log out. Please check your connection and try again.");
        }
    }, [refetch, showError]);
}
