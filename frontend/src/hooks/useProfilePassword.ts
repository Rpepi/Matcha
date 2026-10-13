import { useCallback, useState } from "react";
import { changePassword } from "@/api/profile";
import { useToast } from "@/context/ToastContext";

export function useProfilePassword() {
    const { showNotice } = useToast();
    const [isEditing, setIsEditing] = useState(false);
    const [isSaving, setIsSaving] = useState(false);
    const [current, setCurrent] = useState("");
    const [next, setNext] = useState("");
    const [formError, setFormError] = useState("");

    const reset = useCallback(() => {
        setCurrent("");
        setNext("");
        setFormError("");
    }, []);

    const startEditing = useCallback(() => {
        reset();
        setIsEditing(true);
    }, [reset]);

    const cancelEditing = useCallback(() => {
        reset();
        setIsEditing(false);
    }, [reset]);

    const save = useCallback(async () => {
        setIsSaving(true);
        setFormError("");
        try {
            const response = await changePassword(current, next);
            if (!response.ok) {
                const data = await response.json().catch(() => null);
                setFormError(typeof data?.detail === "string" ? data.detail : "Could not change your password. Please try again.");
                return;
            }
            reset();
            setIsEditing(false);
            showNotice("Password changed. Your other sessions were logged out.");
        } catch {
            setFormError("Could not change your password. Please check your connection and try again.");
        } finally {
            setIsSaving(false);
        }
    }, [current, next, reset, showNotice]);

    return { isEditing, isSaving, current, setCurrent, next, setNext, formError, startEditing, cancelEditing, save };
}
