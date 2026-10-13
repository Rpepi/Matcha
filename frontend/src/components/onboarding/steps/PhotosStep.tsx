import StepPanel from "../StepPanel";
import PhotoGrid from "@/components/PhotoGrid";
import type { OnboardingPhoto } from "../../../hooks/useOnboarding";

interface PhotosStepProps {
    photos: OnboardingPhoto[];
    isUploading: boolean;
    onUpload: (file: File) => void;
    onDelete: (position: number) => void;
    onBack: () => void;
    onNext: () => void;
}

export default function PhotosStep({ photos, isUploading, onUpload, onDelete, onBack, onNext }: PhotosStepProps) {
    // The first photo is the profile picture (the server makes the lowest slot the profile photo).
    const firstPosition = Math.min(...photos.map((p) => p.position));
    const withProfileBadge = photos.map((p) => ({ ...p, isProfile: p.position === firstPosition }));

    return (
        <StepPanel
            title="Add your photos"
            subtitle="Upload 1 to 5 photos. The first one is your profile picture, needed to like people."
            nextDisabled={photos.length === 0}
            onBack={onBack}
            onNext={onNext}
        >
            <div className="mb-7">
                <PhotoGrid photos={withProfileBadge} isUploading={isUploading} onUpload={onUpload} onDelete={onDelete} />
            </div>
        </StepPanel>
    );
}
