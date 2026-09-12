import { STEP_COUNT } from "../../hooks/useOnboarding";

export default function StepProgress({ step }: { step: number }) {
    return (
        <div className="mb-8 flex gap-1.5">
            {Array.from({ length: STEP_COUNT }).map((_, i) => (
                <span
                    key={i}
                    className={`h-1 flex-1 rounded-full transition-colors duration-300 ${
                        i <= step ? "bg-matcha" : "bg-grey/20"
                    }`}
                />
            ))}
        </div>
    );
}
