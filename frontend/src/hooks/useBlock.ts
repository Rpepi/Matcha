import { useCallback, useRef, useState } from "react";
import { blockUser } from "@/api/block";
import { useProfileContext } from "@/context/ProfileContext";
import { useToast } from "@/context/ToastContext";

/**
 * Block one user. Resolves true once the server has recorded the block, after
 * `onBlocked` ran; the caller decides where to go next (the profile and the
 * conversation are both gone from the blocker's point of view).
 */
export function useBlock(userId: number, firstName: string, onBlocked: () => void) {
    const { refetch: refetchProfile } = useProfileContext();
    const { showError, showNotice } = useToast();
    const [isBlocking, setIsBlocking] = useState(false);
    const inFlight = useRef(false);

    const block = useCallback(async (): Promise<boolean> => {
        if (inFlight.current) return false;
        inFlight.current = true;
        setIsBlocking(true);

        try {
            const response = await blockUser(userId);

            if (response.ok) {
                showNotice(`${firstName} has been blocked.`);
                onBlocked();
                return true;
            }

            if (response.status === 401) {
                void refetchProfile(); // session expired: the route guard sends the user to /login
            } else if (response.status === 429) {
                showError("You're doing that too fast. Please wait a moment and try again.");
            } else if (response.status === 404) {
                showError("This profile is no longer available.");
            } else {
                showError("Could not block this user. Please try again.");
            }
            return false;
        } catch {
            showError("Network error. Check your connection and try again.");
            return false;
        } finally {
            inFlight.current = false;
            setIsBlocking(false);
        }
    }, [userId, firstName, onBlocked, refetchProfile, showError, showNotice]);

    return { block, isBlocking };
}
