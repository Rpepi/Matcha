import { useEffect, useRef } from "react";
import { AnimatePresence, motion } from "motion/react";
import { Loader2 } from "lucide-react";
import { useBrowseProfiles } from "@/hooks/useBrowseProfiles";
import { useItemsPerScreen } from "@/hooks/useItemsPerScreen";
import ProfileCard from "@/components/ProfileCard";
import { ROW_MAX_WIDTH, MIN_GAP, CARD_WIDTH } from "@/lib/browseLayout";

const STAGGER_SECONDS = 0;
const SLIDE_SECONDS = 0.4;
const EXIT_EXTRA_DELAY_SECONDS = 0.1;

function transitionDurationMs(cardCount: number): number {
    return (cardCount - 1) * STAGGER_SECONDS * 1000 + EXIT_EXTRA_DELAY_SECONDS * 1000 + SLIDE_SECONDS * 1000;
}

const cardVariants = {
    hidden: { y: "100vh",
		opacity: 0,
	 },
    visible: (i: number) => ({
        y: 0,
		opacity: 1,
        transition: { delay: i * STAGGER_SECONDS, duration: SLIDE_SECONDS, ease: "easeOut" as const },
    }),
    exit: (i: number) => ({
        y: "-100vh",
		opacity: 0,
        transition: { delay: i * STAGGER_SECONDS + EXIT_EXTRA_DELAY_SECONDS, duration: SLIDE_SECONDS },
    }),
};

export default function BrowsePage() {
    const { profiles, cursor, advance, hasMore, isLoading, error, loadMore } = useBrowseProfiles();
    const itemsPerScreen = useItemsPerScreen();
    const lastWheelAt = useRef(0);

    const batch = profiles.slice(cursor, cursor + itemsPerScreen);

    useEffect(() => {
        const previousOverflow = document.body.style.overflow;
        document.body.style.overflow = "hidden";
        return () => {
            document.body.style.overflow = previousOverflow;
        };
    }, []);

    useEffect(() => {
        if (profiles.length > 0 && !isLoading && hasMore && cursor + itemsPerScreen >= profiles.length) {
            loadMore();
        }
    }, [profiles.length, cursor, itemsPerScreen, hasMore, isLoading, loadMore]);

    useEffect(() => {
        function handleWheel(event: WheelEvent) {
            if (event.deltaY <= 0) return;

            const now = Date.now();
            if (now - lastWheelAt.current < transitionDurationMs(batch.length)) return;

            const wouldExceedBuffer = cursor + itemsPerScreen >= profiles.length;
            if (wouldExceedBuffer && (isLoading || !hasMore)) return;

            lastWheelAt.current = now;
            advance(itemsPerScreen);
        }

        window.addEventListener("wheel", handleWheel);
        return () => window.removeEventListener("wheel", handleWheel);
    }, [cursor, itemsPerScreen, profiles.length, hasMore, isLoading, advance, batch.length]);

    return (
        <div className="flex min-h-[calc(100dvh-5rem)] flex-col items-center justify-center p-6 md:min-h-dvh">
            {error && <p className="text-sm text-red-600">{error}</p>}

            {!error && batch.length === 0 && isLoading && <Loader2 className="h-6 w-6 animate-spin text-matcha" />}

            {!error && batch.length === 0 && !isLoading && (
                <p className="text-sm text-grey">No profiles match right now.</p>
            )}

            <div
                className={`flex w-full ${batch.length > 1 ? "justify-between" : "justify-center"}`}
                style={{ maxWidth: ROW_MAX_WIDTH, gap: MIN_GAP }}
            >
                <AnimatePresence mode="popLayout" initial={false} key={itemsPerScreen}>
                    {batch.map((profile, i) => (
                        <motion.div
                            key={profile.id}
                            custom={i}
                            variants={cardVariants}
                            initial="hidden"
                            animate="visible"
                            exit="exit"
                            className="min-w-0"
                            style={{ flex: `0 1 ${CARD_WIDTH}px` }}
                        >
                            <ProfileCard profile={profile} />
                        </motion.div>
                    ))}
                </AnimatePresence>
            </div>
        </div>
    );
}
