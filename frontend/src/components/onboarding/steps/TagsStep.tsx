import { useState, useEffect } from "react";
import { Loader2 } from "lucide-react";
import StepPanel from "../StepPanel";
import { getAvailableTags } from "../../../api/tags";

const MAX_TAGS = 5;

interface TagsStepProps {
    tags: string[];
    setTags: (value: string[]) => void;
    onBack: () => void;
    onNext: () => void;
}

export default function TagsStep({ tags, setTags, onBack, onNext }: TagsStepProps) {
    const [availableTags, setAvailableTags] = useState<string[]>([]);
    const [isLoadingTags, setIsLoadingTags] = useState(true);

    useEffect(() => {
        getAvailableTags()
            .then(async (res) => {
                if (!res.ok) return;
                const data = await res.json();
                if (Array.isArray(data.tags)) setAvailableTags(data.tags);
            })
            .finally(() => setIsLoadingTags(false));
    }, []);

    function toggleTag(tag: string) {
        if (tags.includes(tag)) {
            setTags(tags.filter((t) => t !== tag));
        } else if (tags.length < MAX_TAGS) {
            setTags([...tags, tag]);
        }
    }

    return (
        <StepPanel
            title="What are you into?"
            subtitle={`Pick up to ${MAX_TAGS} interests.`}
            nextDisabled={tags.length === 0}
            onBack={onBack}
            onNext={onNext}
        >
            <div className="flex flex-wrap gap-2 mb-7">
                {isLoadingTags && (
                    <Loader2 className="h-5 w-5 animate-spin text-matcha" />
                )}
                {!isLoadingTags && availableTags.length === 0 && (
                    <p className="text-sm text-ink/50">Could not load interests. Please try again later.</p>
                )}
                {availableTags.map((tag) => {
                    const isSelected = tags.includes(tag);
                    const isDisabled = !isSelected && tags.length >= MAX_TAGS;
                    return (
                        <button
                            key={tag}
                            type="button"
                            disabled={isDisabled}
                            onClick={() => toggleTag(tag)}
                            className={`rounded-full border-3 px-3.5 py-1.5 text-sm font-medium transition ${
                                isSelected
                                    ? "border-matcha-dark bg-matcha-dark text-matcha"
                                    : isDisabled
                                        ? "border-grey/15 text-grey/30"
                                        : "border-grey/20 text-matcha-dark hover:border-matcha-dark hover:text-matcha-dark"
                            }`}
                        >
                            #{tag}
                        </button>
                    );
                })}
            </div>
        </StepPanel>
    );
}
