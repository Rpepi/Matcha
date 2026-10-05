import { useCallback, useState } from "react";
import { useProfileContext } from "@/context/ProfileContext";
import { useToast } from "@/context/ToastContext";
import { updateProfile } from "@/api/profile";

export function useProfileBio(bio: string | null) {
    const { refetch } = useProfileContext();
    const { showError } = useToast();
    const [isEditing, setIsEditing] = useState(false);
    const [isSaving, setIsSaving] = useState(false);
    const [draft, setDraft] = useState(bio ?? "");

    const startEditing = useCallback(() => {
        setDraft(bio ?? "");
        setIsEditing(true);
    }, [bio]);

    const cancelEditing = useCallback(() => setIsEditing(false), []);

    const save = useCallback(async () => {
        setIsSaving(true);
        try {
            const response = await updateProfile({ bio: draft });
            if (!response.ok) {
                const data = await response.json().catch(() => null);
                showError(data?.detail ?? "Could not save your bio. Please try again.");
                return;
            }
            await refetch();
            setIsEditing(false);
        } catch {
            showError("Could not save your bio. Please check your connection and try again.");
        } finally {
            setIsSaving(false);
        }
    }, [draft, refetch, showError]);

    return { isEditing, isSaving, draft, setDraft, startEditing, cancelEditing, save };
}
