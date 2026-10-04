import { motion } from "motion/react";
import { Heart } from "lucide-react";

interface LikeButtonProps {
    liked: boolean;
    isPending: boolean;
    onToggle: () => void;
    name: string;
    /** `icon`: round button for photos and cards. `pill`: labelled, for the profile page. */
    variant?: "icon" | "pill";
    /** False when liking is known to be refused: dimmed, but still clickable so it can say why. */
    canLike?: boolean;
    className?: string;
}

const focusClasses =
    "focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-matcha";

export default function LikeButton({ liked, isPending, onToggle, name, variant = "icon", canLike = true, className = "" }: LikeButtonProps) {
    const dim = canLike ? "" : "opacity-60";
    const heart = (
        // Pops when it becomes liked. Animated in place: re-mounting the icon on each change made it flash.
        <motion.span
            initial={false}
            animate={{ scale: liked ? [1, 1.3, 1] : 1 }}
            transition={{ duration: 0.3 }}
            className="flex"
        >
            <Heart className={`h-5 w-5 ${liked ? "fill-pink text-pink" : "text-ink"}`} aria-hidden="true" />
        </motion.span>
    );

    if (variant === "pill") {
        return (
            <motion.button
                type="button"
                onClick={onToggle}
                // The visible text already says "Like" / "Liked": adding aria-pressed would announce the state twice.
                aria-busy={isPending}
                aria-disabled={!canLike || undefined}
                whileTap={{ scale: 0.95 }}
                className={`flex cursor-pointer items-center gap-2 rounded-full px-6 py-3 font-medium text-ink transition ${focusClasses} ${
                    liked ? "bg-pink/15 hover:bg-pink/25" : "bg-matcha hover:brightness-95"
                } ${dim} ${className}`}
            >
                {heart}
                {liked ? "Liked" : "Like"}
                <span className="sr-only"> {name}</span>
            </motion.button>
        );
    }

    return (
        <motion.button
            type="button"
            onClick={onToggle}
            aria-pressed={liked}
            aria-busy={isPending}
            aria-disabled={!canLike || undefined}
            // Fixed name + aria-pressed: a changing name on top of the pressed state reads as a contradiction.
            aria-label={`Like ${name}`}
            whileTap={{ scale: 0.88 }}
            className={`flex h-11 w-11 shrink-0 cursor-pointer items-center justify-center rounded-full bg-paper/90 transition hover:bg-paper ${focusClasses} ${dim} ${className}`}
        >
            {heart}
        </motion.button>
    );
}
