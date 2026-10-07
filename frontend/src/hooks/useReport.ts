import { useCallback, useRef, useState } from "react";
import { reportUser } from "@/api/report";
import { useProfileContext } from "@/context/ProfileContext";
import { useToast } from "@/context/ToastContext";

/**
 * Report one user for abuse. Resolves true once the server has recorded (or
 * already had) the report; the caller just closes the dialog either way.
 */
export function useReport(userId: number, firstName: string) {
    const { refetch: refetchProfile } = useProfileContext();
    const { showError, showNotice } = useToast();
    const [isReporting, setIsReporting] = useState(false);
    const inFlight = useRef(false);

    const report = useCallback(async (reason: string): Promise<boolean> => {
        if (inFlight.current) return false;
        inFlight.current = true;
        setIsReporting(true);

        try {
            const response = await reportUser(userId, reason.trim() || null);

            if (response.ok) {
                const { message } = await response.json();
                showNotice(
                    message === "already reported"
                        ? `You've already reported ${firstName}.`
                        : `${firstName} has been reported.`,
                );
                return true;
            }

            if (response.status === 401) {
                void refetchProfile(); // session expired: the route guard sends the user to /login
            } else if (response.status === 429) {
                showError("You're doing that too fast. Please wait a moment and try again.");
            } else if (response.status === 404) {
                showError("This profile is no longer available.");
            } else {
                showError("Could not report this user. Please try again.");
            }
            return false;
        } catch {
            showError("Network error. Check your connection and try again.");
            return false;
        } finally {
            inFlight.current = false;
            setIsReporting(false);
        }
    }, [userId, firstName, refetchProfile, showError, showNotice]);

    return { report, isReporting };
}
