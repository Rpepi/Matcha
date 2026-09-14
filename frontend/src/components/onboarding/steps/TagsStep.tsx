import StepPanel from "../StepPanel";

const MAX_TAGS = 5;

const AVAILABLE_TAGS = [
    "Travel", "Coffee", "Hiking", "Movies", "Music", "Gaming", "Fitness",
    "Foodie", "Art", "Photography", "Dogs", "Cats", "Yoga", "Reading",
    "Dancing", "Cooking", "Wine", "Beach", "Nature", "Tech",
];

interface TagsStepProps {
    tags: string[];
    setTags: (value: string[]) => void;
    onBack: () => void;
    onNext: () => void;
}

export default function TagsStep({ tags, setTags, onBack, onNext }: TagsStepProps) {
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
                {AVAILABLE_TAGS.map((tag) => {
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
