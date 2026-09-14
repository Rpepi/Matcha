import { useRef, type ChangeEvent } from "react";
import { Trash2, ImageIcon } from "lucide-react";
import StepPanel from "../StepPanel";
import type { OnboardingPhoto } from "../../../hooks/useOnboarding";

const SLOT_COUNT = 5;

interface PhotosStepProps {
    isActive: boolean;
    photos: OnboardingPhoto[];
    isUploading: boolean;
    onUpload: (file: File) => void;
    onDelete: (position: number) => void;
    onBack: () => void;
    onNext: () => void;
}

export default function PhotosStep({ isActive, photos, isUploading, onUpload, onDelete, onBack, onNext }: PhotosStepProps) {
    const inputRef = useRef<HTMLInputElement>(null);

    function handleFileChange(e: ChangeEvent<HTMLInputElement>) {
        const file = e.target.files?.[0];
        if (file) onUpload(file);
        e.target.value = '';
    }

    return (
        <StepPanel
            title="Add your photos"
            subtitle="Upload at least 1 photo so people can see who they're matching with."
            nextDisabled={photos.length === 0}
            onBack={onBack}
            onNext={onNext}
            isActive={isActive}
        >
            <input
                ref={inputRef}
                type="file"
                accept="image/*"
                className="hidden"
                onChange={handleFileChange}
            />
            <div className="grid grid-cols-3 gap-3 mb-7">
                {Array.from({ length: SLOT_COUNT }).map((_, i) => {
                    const photo = photos[i];
                    if (photo) {
                        return (
                            <div
                                key={`photo-${photo.position}`}
                                className="group relative aspect-square overflow-hidden rounded-xl border border-grey/30"
                            >
                                {photo.url ? (
                                    <img src={photo.url} alt="" className="h-full w-full object-cover" />
                                ) : (
                                    <div className="flex h-full w-full items-center justify-center bg-grey/10 text-grey/40">
                                        <ImageIcon className="h-6 w-6" />
                                    </div>
                                )}
                                <button
                                    type="button"
                                    onClick={() => onDelete(photo.position)}
                                    aria-label="Remove photo"
                                    className="absolute top-1.5 right-1.5 rounded-full bg-ink/60 p-1.5 text-paper opacity-0 transition group-hover:opacity-100 hover:bg-ink/80"
                                >
                                    <Trash2 className="h-4 w-4" />
                                </button>
                            </div>
                        );
                    }

                    const isNextSlot = i === photos.length;
                    return (
                        <button
                            key={`slot-${i}`}
                            type="button"
                            disabled={!isNextSlot || isUploading}
                            onClick={() => inputRef.current?.click()}
                            className={`aspect-square rounded-xl border-3 border-dashed text-2xl transition ${
                                isNextSlot
                                    ? "cursor-pointer border-grey/40 text-grey/60 hover:border-matcha hover:text-matcha"
                                    : "border-grey/15 text-grey/20"
                            }`}
                        >
                            +
                        </button>
                    );
                })}
            </div>
        </StepPanel>
    );
}
