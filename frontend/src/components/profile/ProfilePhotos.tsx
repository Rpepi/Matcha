import { useState } from "react";
import type { Profile } from "@/context/ProfileContext";
import { useProfileContext } from "@/context/ProfileContext";
import { useToast } from "@/context/ToastContext";
import { uploadPhoto as uploadPhotoApi, deletePhoto as deletePhotoApi, movePhoto as movePhotoApi } from "@/api/photos";
import PhotoGrid from "@/components/PhotoGrid";

export default function ProfilePhotos({ photos }: { photos: Profile["photos"] }) {
    const { refetch } = useProfileContext();
    const { showError } = useToast();
    const [isUploading, setIsUploading] = useState(false);

    const gridPhotos = photos
        .map((photo) => ({
            position: photo.position,
            url: `/api/profile/photos/${photo.position}?v=${encodeURIComponent(photo.path)}`,
        }))
        .sort((a, b) => a.position - b.position);

    async function handleUpload(file: File) {
        setIsUploading(true);
        const response = await uploadPhotoApi(file);
        setIsUploading(false);
        if (!response.ok) {
            const data = await response.json().catch(() => null);
            showError(data?.detail ?? "Could not upload photo. Please try again.");
            return;
        }
        await refetch();
    }

    async function handleDelete(position: number) {
        const response = await deletePhotoApi(position);
        if (!response.ok) {
            const data = await response.json().catch(() => null);
            showError(data?.detail ?? "Could not delete photo. Please try again.");
            return;
        }

        // The backend leaves a gap at the deleted position: close it by shifting every
        // later photo down one slot, same as onboarding's photo step does.
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
    }

    return (
        <div className="flex flex-col gap-3">
            <h2 className="text-xs font-semibold tracking-widest text-grey uppercase">Photos</h2>
            <PhotoGrid photos={gridPhotos} isUploading={isUploading} onUpload={handleUpload} onDelete={handleDelete} />
        </div>
    );
}
