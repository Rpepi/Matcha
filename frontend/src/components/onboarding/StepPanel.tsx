import type { ReactNode } from "react";
import { ArrowLeft } from "lucide-react";
import { Button } from "../FormControls";

interface StepPanelProps {
    title: string;
    subtitle?: string;
    children: ReactNode;
    onBack?: () => void;
    onNext: () => void;
    nextLabel?: string;
    nextDisabled?: boolean;
    isLoading?: boolean;
}

export default function StepPanel({ title, subtitle, children, onBack, onNext, nextLabel = "Continue", nextDisabled, isLoading }: StepPanelProps) {
    return (
        <div className="relative w-full px-0.5">
            {onBack && (
                <button
                    type="button"
                    onClick={onBack}
                    aria-label="Back"
                    className="absolute top-0 left-0 z-10 rounded-full p-2 text-ink/60 transition hover:text-ink"
                >
                    <ArrowLeft className="h-5 w-5" />
                </button>
            )}

            <div className={`animate-in fade-in duration-300 ${onBack ? "pt-9" : ""}`}>
                <h2 className="font-display text-2xl font-medium text-ink">{title}</h2>
                {subtitle && <p className="mt-1.5 text-sm text-ink/60">{subtitle}</p>}

                <div className="mt-6 min-h-24">{children}</div>
            </div>

            <div className="">
                <Button
                    type="button"
                    onClick={onNext}
                    disabled={nextDisabled || isLoading}
                    className="w-full"
                >
                    {isLoading ? "Saving…" : nextLabel}
                </Button>
            </div>
        </div>
    );
}
