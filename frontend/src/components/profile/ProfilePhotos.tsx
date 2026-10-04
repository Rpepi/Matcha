import type { Profile } from "@/context/ProfileContext";
import { useProfilePhotos } from "@/hooks/useProfilePhotos";
import PhotoGrid from "@/components/PhotoGrid";

export default function ProfilePhotos({ photos }: { photos: Profile["photos"] }) {
    const { gridPhotos, isUploading, handleUpload, handleDelete } = useProfilePhotos(photos);

    return (
        <div className="flex flex-col gap-3">
            <h2 className="text-xs font-semibold tracking-widest text-grey uppercase">Photos</h2>
            <PhotoGrid photos={gridPhotos} isUploading={isUploading} onUpload={handleUpload} onDelete={handleDelete} />
        </div>
    );
}
