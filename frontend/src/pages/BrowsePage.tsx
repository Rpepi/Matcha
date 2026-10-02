import { AnimatePresence, motion } from "motion/react";
import { Loader2 } from "lucide-react";
import { useBrowseProfiles } from "@/hooks/useBrowseProfiles";
import { useItemsPerScreen } from "@/hooks/useItemsPerScreen";
import { useLockBodyScroll } from "@/hooks/useLockBodyScroll";
import { useWheelAdvance } from "@/hooks/useWheelAdvance";
import ProfileCard from "@/components/ProfileCard";
import { ROW_MAX_WIDTH, MIN_GAP, CARD_WIDTH } from "@/lib/browseLayout";
import { cardVariants } from "@/lib/browseAnimation";

export default function BrowsePage() {
    const itemsPerScreen = useItemsPerScreen();
    const { profiles, cursor, advance, hasMore, isLoading, error } = useBrowseProfiles(itemsPerScreen);
    const batch = profiles.slice(cursor, cursor + itemsPerScreen);

    useLockBodyScroll();
    useWheelAdvance({
        cursor,
        itemsPerScreen,
        bufferedCount: profiles.length,
        batchSize: batch.length,
        hasMore,
        isLoading,
        advance,
    });

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
