import type { ReactNode } from "react";
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
    isActive: boolean;
}

export default function StepPanel({ title, subtitle, children, onBack, onNext, nextLabel = "Continue", nextDisabled, isLoading, isActive }: StepPanelProps) {
    return (
        <div className="w-full shrink-0 px-0.5" aria-hidden={!isActive} inert={!isActive}>
            <h2 className="font-display text-2xl font-medium text-plum">{title}</h2>
            {subtitle && <p className="mt-1.5 text-sm text-plum/60">{subtitle}</p>}

            <div className="mt-6 min-h-24">{children}</div>

            <div className="mt-8 flex items-center gap-3">
                {onBack && (
                    <button
                        type="button"
                        onClick={onBack}
                        className="rounded-xl px-4 py-2.5 text-sm font-medium text-plum/60 transition hover:text-plum"
                    >
                        Back
                    </button>
                )}
                <Button
                    type="button"
                    onClick={onNext}
                    disabled={nextDisabled || isLoading}
                    className="flex-1"
                >
                    {isLoading ? "Saving…" : nextLabel}
                </Button>
            </div>
        </div>
    );
}
