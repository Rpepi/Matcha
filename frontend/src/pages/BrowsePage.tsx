import { useEffect } from "react";
import { AnimatePresence, motion } from "motion/react";
import { Loader2 } from "lucide-react";
import { useBrowseContext } from "@/context/BrowseContext";
import { useLockBodyScroll } from "@/hooks/useLockBodyScroll";
import { useWheelAdvance } from "@/hooks/useWheelAdvance";
import { useToast } from "@/context/ToastContext";
import ProfileCard from "@/components/ProfileCard";
import BrowseFilterButton from "@/components/browse/BrowseFilterButton";
import { ROW_MAX_WIDTH, MIN_GAP, CARD_WIDTH } from "@/lib/browseLayout";
import { cardVariants } from "@/lib/browseAnimation";

export default function BrowsePage() {
    const { itemsPerScreen, profiles, cursor, direction, advance, goBack, isLoading, error, atEnd } = useBrowseContext();
    const batch = profiles.slice(cursor, cursor + itemsPerScreen);
    const { showNotice } = useToast();

    useLockBodyScroll();
    useWheelAdvance({ batchSize: batch.length, advance, goBack });

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
            </div>
        </div>
    );
}
