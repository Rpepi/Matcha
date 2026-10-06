import { useCallback, useState } from "react";
import type { Profile } from "@/context/ProfileContext";
import { useProfileContext } from "@/context/ProfileContext";
import { useToast } from "@/context/ToastContext";
import { uploadPhoto as uploadPhotoApi, deletePhoto as deletePhotoApi, movePhoto as movePhotoApi } from "@/api/photos";

export function useProfilePhotos(photos: Profile["photos"]) {
    const { refetch } = useProfileContext();
    const { showError } = useToast();
    const [isUploading, setIsUploading] = useState(false);

    const gridPhotos = photos
        .map((photo) => ({
            position: photo.position,
            url: `/api/profile/photos/${photo.position}?v=${encodeURIComponent(photo.path)}`,
        }))
        .sort((a, b) => a.position - b.position);

    const handleUpload = useCallback(
        async (file: File) => {
            setIsUploading(true);
            try {
                const response = await uploadPhotoApi(file);
                if (!response.ok) {
                    const data = await response.json().catch(() => null);
                    showError(data?.detail ?? "Could not upload photo. Please try again.");
                    return;
                }
                await refetch();
            } catch {
                showError("Could not upload photo. Please check your connection and try again.");
            } finally {
                setIsUploading(false);
            }
        },
        [refetch, showError],
    );

    const handleDelete = useCallback(
        async (position: number) => {
            try {
                const response = await deletePhotoApi(position);
                if (!response.ok) {
                    const data = await response.json().catch(() => null);
                    showError(data?.detail ?? "Could not delete photo. Please try again.");
                    return;
                }

                const remaining = photos.filter((p) => p.position !== position).sort((a, b) => a.position - b.position);
                for (const photo of remaining) {
                    if (photo.position <= position) continue;
                    const moveResponse = await movePhotoApi(photo.position, photo.position - 1);
                    if (!moveResponse.ok) {
                        const data = await moveResponse.json().catch(() => null);
                        showError(data?.detail ?? "Could not reorder photos. Please try again.");
                        break;
                    }
                }
                await refetch();
            } catch {
                showError("Could not delete photo. Please check your connection and try again.");
            }
        },
        [photos, refetch, showError],
    );

    return { gridPhotos, isUploading, handleUpload, handleDelete };
}
