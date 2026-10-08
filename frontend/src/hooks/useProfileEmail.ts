import { useCallback, useState } from "react";
import type { Profile } from "@/context/ProfileContext";
import { useProfileContext } from "@/context/ProfileContext";
import { useToast } from "@/context/ToastContext";
import { cancelPendingEmail, resendPendingEmail, updateProfile } from "@/api/profile";

type EmailFields = Pick<Profile, "email" | "pending_email">;

const FALLBACK_ERRORS: Record<number, string> = {
    429: "You've asked for too many email changes. Please try again later.",
};

/**
 * Change the email with a confirmation step: the API only stores the new address
 * as pending and mails it a link, the current email keeps working until it is
 * clicked. The form's own error (shown under the field) carries the API's
 * message, including the 429 "Too many email changes, try again later".
 */
export function useProfileEmail({ email, pending_email }: EmailFields) {
    const { refetch } = useProfileContext();
    const { showError, showNotice } = useToast();
    const [isEditing, setIsEditing] = useState(false);
    const [isSaving, setIsSaving] = useState(false);
    const [isBusy, setIsBusy] = useState(false);
    const [draft, setDraft] = useState("");
    const [formError, setFormError] = useState("");

    const startEditing = useCallback(() => {
        setDraft(pending_email ?? email);
        setFormError("");
        setIsEditing(true);
    }, [email, pending_email]);

    const cancelEditing = useCallback(() => {
        setFormError("");
        setIsEditing(false);
    }, []);

    const save = useCallback(async () => {
        const next = draft.trim();
        if (!next) {
            setFormError("Enter the new email address.");
            return;
        }
        const sameAsActive = next.toLowerCase() === email.toLowerCase();
        if (sameAsActive && !pending_email) {
            setIsEditing(false); // nothing to change
            return;
        }

        setIsSaving(true);
        setFormError("");
        try {
            const response = await updateProfile({ email: next });
            const data = await response.json().catch(() => null);
            if (!response.ok) {
                setFormError(data?.detail ?? FALLBACK_ERRORS[response.status] ?? "Could not change your email. Please try again.");
                return;
            }
            await refetch();
            setIsEditing(false);
            if (sameAsActive) {
                showNotice("Email change cancelled.");
            } else if (typeof data?.message === "string" && data.message.includes("could not be sent")) {
                showError("Saved, but we could not send the confirmation email. Use “Resend link” to try again.");
            } else {
                showNotice(`We sent a confirmation link to ${next}. Your email changes once you click it.`);
            }
        } catch {
            setFormError("Could not change your email. Please check your connection and try again.");
        } finally {
            setIsSaving(false);
        }
    }, [draft, email, pending_email, refetch, showError, showNotice]);

    const resend = useCallback(async () => {
        setIsBusy(true);
        try {
            const response = await resendPendingEmail();
            if (response.ok) {
                showNotice(`Confirmation link sent again to ${pending_email}.`);
                return;
            }
            if (response.status === 404) await refetch(); // the change is gone (cancelled elsewhere): drop the banner
            const data = await response.json().catch(() => null);
            showError(data?.detail ?? FALLBACK_ERRORS[response.status] ?? "Could not send the email. Please try again.");
        } catch {
            showError("Could not send the email. Please check your connection and try again.");
        } finally {
            setIsBusy(false);
        }
    }, [pending_email, refetch, showError, showNotice]);

    const cancelPending = useCallback(async () => {
        setIsBusy(true);
        try {
            const response = await cancelPendingEmail();
            if (!response.ok) {
                const data = await response.json().catch(() => null);
                showError(data?.detail ?? "Could not cancel the change. Please try again.");
                return;
            }
            await refetch();
            showNotice("Email change cancelled.");
        } catch {
            showError("Could not cancel the change. Please check your connection and try again.");
        } finally {
            setIsBusy(false);
        }
    }, [refetch, showError, showNotice]);

    return { isEditing, isSaving, isBusy, draft, setDraft, formError, startEditing, cancelEditing, save, resend, cancelPending };
}
