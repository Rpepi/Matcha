import { useEffect } from "react";
import { AnimatePresence, motion } from "motion/react";
import { ChevronLeft, ChevronRight, Loader2 } from "lucide-react";
import { useBrowseContext } from "@/context/BrowseContext";
import { useLockBodyScroll } from "@/hooks/useLockBodyScroll";
import { useBrowseNavigation } from "@/hooks/useBrowseNavigation";
import { useToast } from "@/context/ToastContext";
import ProfileCard from "@/components/ProfileCard";
import BrowseFilterButton from "@/components/browse/BrowseFilterButton";
import { ROW_MAX_WIDTH, MIN_GAP, CARD_WIDTH } from "@/lib/browseLayout";
import { cardVariants } from "@/lib/browseAnimation";

// Same look as the arrows of the profile photo gallery. Centred on the edges of
// the card row, so on a phone they sit in the margin beside the single card.
const navButtonClasses =
    "absolute top-1/2 z-10 flex h-11 w-11 -translate-y-1/2 cursor-pointer items-center justify-center rounded-full bg-paper/90 text-ink shadow-md shadow-ink/10 transition hover:bg-paper focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-matcha";

export default function BrowsePage() {
    const { itemsPerScreen, profiles, cursor, direction, advance, goBack, isLoading, error, atEnd } = useBrowseContext();
    const batch = profiles.slice(cursor, cursor + itemsPerScreen);
    const { showNotice } = useToast();

    useLockBodyScroll();
    const { next, previous } = useBrowseNavigation({ batchSize: batch.length, advance, goBack });

    useEffect(() => {
        if (atEnd) showNotice("That's everyone for now — check back later.");
    }, [atEnd, showNotice]);

    return (
        <div className="flex min-h-[calc(100dvh-5rem)] flex-col items-center justify-center overflow-x-clip p-6 md:min-h-dvh">
            <BrowseFilterButton />

            {!error && batch.length === 0 && isLoading && <Loader2 className="h-6 w-6 animate-spin text-matcha" />}

            {!error && batch.length === 0 && !isLoading && (
                <p className="text-sm text-grey">No profiles match right now.</p>
            )}

            <div
                className={`relative flex w-full ${batch.length > 1 ? "justify-between" : "justify-center"}`}
                style={{ maxWidth: ROW_MAX_WIDTH, gap: MIN_GAP }}
            >
                <AnimatePresence mode="popLayout" initial={false} key={itemsPerScreen} custom={{ direction }}>
                    {batch.map((profile, i) => (
                        <motion.div
                            key={profile.id}
                            custom={{ index: i, direction }}
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

                {/* The wheel, a swipe or the arrow keys do the same; these make it visible, and work everywhere */}
                {cursor > 0 && (
                    <button
                        type="button"
                        onClick={previous}
                        aria-label="Previous profiles"
                        className={`left-0 -translate-x-1/2 ${navButtonClasses}`}
                    >
                        <ChevronLeft className="h-5 w-5" />
                    </button>
                )}
                {batch.length > 0 && !atEnd && (
                    <button
                        type="button"
                        onClick={next}
                        aria-label="Next profiles"
                        className={`right-0 translate-x-1/2 ${navButtonClasses}`}
                    >
                        <ChevronRight className="h-5 w-5" />
                    </button>
                )}
            </div>
        </div>
    );
}
