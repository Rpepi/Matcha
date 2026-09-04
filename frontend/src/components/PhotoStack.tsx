import type { ReactNode } from "react"

interface PhantomCardProps {
    rotate: string
    x: string
    y: string
    tone: string
}

function PhantomCard({ rotate, x, y, tone }: PhantomCardProps) {
    return (
        <div
            aria-hidden="true"
            className={`absolute inset-0 rounded-[1.75rem] bg-gradient-to-br ${tone} opacity-90 shadow-xl shadow-black/30 motion-safe:animate-[drift_7s_ease-in-out_infinite]`}
            style={{ transform: `translate(${x}, ${y}) rotate(${rotate})` }}
        >
            <div className="absolute inset-4 rounded-2xl border border-white/15" />
        </div>
    );
}

interface PhotoStackProps {
    frontSlot?: ReactNode
    className?: string
}

export default function PhotoStack({ frontSlot, className = "" }: PhotoStackProps) {
    return (
        <div className={`relative h-72 w-64 sm:h-80 sm:w-72 ${className}`}>
            <div
                aria-hidden="true"
                className="absolute inset-0 -z-10 rounded-[3rem] bg-bloom/30 blur-3xl"
            />
            <PhantomCard rotate="-9deg" x="-1.25rem" y="1.25rem" tone="from-orchid to-ink" />
            <PhantomCard rotate="7deg" x="1.5rem" y="0.5rem" tone="from-garnet to-bloom" />
            <div
                className="absolute inset-0 flex rotate-[-2deg] flex-col justify-end overflow-hidden rounded-[1.75rem] border border-white/15 bg-ink/50 shadow-2xl shadow-black/40 backdrop-blur-sm motion-safe:animate-[drift_6s_ease-in-out_infinite]"
            >
                {frontSlot}
            </div>
        </div>
    );
}
