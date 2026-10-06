import { useRef, type ChangeEvent } from "react";
import { Trash2, ImageIcon } from "lucide-react";
import { useToast } from "@/context/ToastContext";

const SLOT_COUNT = 5;
const MAX_FILE_SIZE = 5 * 1024 * 1024;

export interface PhotoGridPhoto {
    position: number;
    url: string | null;
}

interface PhotoGridProps {
    photos: PhotoGridPhoto[];
    isUploading?: boolean;
    onUpload?: (file: File) => void;
    onDelete?: (position: number) => void;
}

export default function PhotoGrid({ photos, isUploading = false, onUpload, onDelete }: PhotoGridProps) {
    const inputRef = useRef<HTMLInputElement>(null);
    const { showError } = useToast();
    const editable = Boolean(onUpload);

    function handleFileChange(e: ChangeEvent<HTMLInputElement>) {
        const file = e.target.files?.[0];
        e.target.value = "";
        if (!file) return;
        if (file.size > MAX_FILE_SIZE) {
            showError("Photo is too large. Max size is 5MB.");
            return;
        }
        onUpload?.(file);
    }

    return (
        <div className="grid grid-cols-3 gap-3">
            {editable && (
                <input
                    ref={inputRef}
                    type="file"
                    accept="image/jpeg,image/png"
                    className="hidden"
                    onChange={handleFileChange}
                />
            )}
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
                            {onDelete && (
                                <button
                                    type="button"
                                    onClick={() => onDelete(photo.position)}
                                    aria-label="Remove photo"
                                    className="absolute top-1.5 right-1.5 rounded-full bg-ink/60 p-1.5 text-paper opacity-0 transition group-hover:opacity-100 hover:bg-ink/80 focus-visible:opacity-100 pointer-coarse:opacity-100"
                                >
                                    <Trash2 className="h-4 w-4" />
                                </button>
                            )}
                        </div>
                    );
                }

                if (!editable) {
                    return (
                        <div
                            key={`empty-${i}`}
                            className="aspect-square rounded-xl border-3 border-dashed border-grey/15"
                        />
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
    );
}
