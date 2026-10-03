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
    return (
        <StepPanel
            title="Add your photos"
            subtitle="Upload at least 1 photo so people can see who they're matching with."
            nextDisabled={photos.length === 0}
            onBack={onBack}
            onNext={onNext}
        >
            <div className="mb-7">
                <PhotoGrid photos={photos} isUploading={isUploading} onUpload={onUpload} onDelete={onDelete} />
            </div>
        </StepPanel>
    );
}
