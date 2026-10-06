import { useCallback, useState } from "react";
import type { Profile } from "@/context/ProfileContext";
import { useProfileContext } from "@/context/ProfileContext";
import { useToast } from "@/context/ToastContext";
import { updateProfile } from "@/api/profile";

export interface ProfileDetailsFields {
    first_name: string;
    last_name: string;
    gender: string;
    orientation: string;
    birth_date: string;
}

function fieldsFrom(profile: Profile): ProfileDetailsFields {
    return {
        first_name: profile.first_name,
        last_name: profile.last_name,
        gender: profile.gender ?? "",
        orientation: profile.orientation ?? "",
        birth_date: profile.birth_date ?? "",
    };
}

export function useProfileDetails(profile: Profile) {
    const { refetch } = useProfileContext();
    const { showError } = useToast();
    const [isEditing, setIsEditing] = useState(false);
    const [isSaving, setIsSaving] = useState(false);
    const [fields, setFields] = useState<ProfileDetailsFields>(() => fieldsFrom(profile));

    const startEditing = useCallback(() => {
        setFields(fieldsFrom(profile));
        setIsEditing(true);
    }, [profile]);

    const cancelEditing = useCallback(() => setIsEditing(false), []);

    const setField = useCallback(<K extends keyof ProfileDetailsFields>(key: K, value: ProfileDetailsFields[K]) => {
        setFields((prev) => ({ ...prev, [key]: value }));
    }, []);

    const save = useCallback(async () => {
        setIsSaving(true);
        try {
            const response = await updateProfile(fields);
            if (!response.ok) {
                const data = await response.json().catch(() => null);
                showError(data?.detail ?? "Could not save your profile. Please try again.");
                return;
            }
            await refetch();
            setIsEditing(false);
        } catch {
            showError("Could not save your profile. Please check your connection and try again.");
        } finally {
            setIsSaving(false);
        }
    }, [fields, refetch, showError]);

    return { isEditing, isSaving, fields, startEditing, cancelEditing, setField, save };
}
