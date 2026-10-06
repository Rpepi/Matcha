import { useCallback, useState } from "react";
import { useProfileContext } from "@/context/ProfileContext";
import { useToast } from "@/context/ToastContext";
import { getAvailableTags, updateTags } from "@/api/tags";

export const MAX_TAGS = 5;

export function useProfileTags(tags: string[]) {
    const { refetch } = useProfileContext();
    const { showError } = useToast();
    const [availableTags, setAvailableTags] = useState<string[]>([]);
    const [isLoadingTags, setIsLoadingTags] = useState(false);
    const [isSaving, setIsSaving] = useState(false);

    const save = useCallback(
        async (nextTags: string[]) => {
            setIsSaving(true);
            try {
                const response = await updateTags(nextTags);
                if (!response.ok) {
                    const data = await response.json().catch(() => null);
                    showError(data?.detail ?? "Could not save your interests. Please try again.");
                    return;
                }
                await refetch();
            } catch {
                showError("Could not save your interests. Please check your connection and try again.");
            } finally {
                setIsSaving(false);
            }
        },
        [refetch, showError],
    );

    const removeTag = useCallback((tag: string) => void save(tags.filter((t) => t !== tag)), [tags, save]);
    const addTag = useCallback((tag: string) => void save([...tags, tag]), [tags, save]);

    const loadAvailableTags = useCallback(() => {
        setIsLoadingTags(true);
        getAvailableTags()
            .then(async (res) => {
                if (!res.ok) return;
                const data = await res.json();
                if (Array.isArray(data.tags)) setAvailableTags(data.tags);
            })
            .finally(() => setIsLoadingTags(false));
    }, []);

    const addableTags = availableTags.filter((tag) => !tags.includes(tag));

    return { isSaving, isLoadingTags, addableTags, loadAvailableTags, addTag, removeTag };
}
