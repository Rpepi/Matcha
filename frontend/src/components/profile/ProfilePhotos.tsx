import type { Profile } from "@/context/ProfileContext";
import PhotoGrid from "@/components/PhotoGrid";

export default function ProfilePhotos({ photos }: { photos: Profile["photos"] }) {
    const gridPhotos = photos
        .map((photo) => ({
            position: photo.position,
            url: `/api/profile/photos/${photo.position}?v=${encodeURIComponent(photo.path)}`,
        }))
        .sort((a, b) => a.position - b.position);

    return <PhotoGrid photos={gridPhotos} />;
}
