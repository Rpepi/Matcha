import { useEffect, useRef } from "react";
import { Loader2 } from "lucide-react";
import { useBrowseProfiles } from "@/hooks/useBrowseProfiles";
import { useItemsPerScreen } from "@/hooks/useItemsPerScreen";
import ProfileCard from "@/components/ProfileCard";
import { ROW_MAX_WIDTH, MIN_GAP } from "@/lib/browseLayout";

const WHEEL_COOLDOWN_MS = 500;

export default function BrowsePage() {
    const { profiles, cursor, advance, hasMore, isLoading, error, loadMore } = useBrowseProfiles();
    const itemsPerScreen = useItemsPerScreen();
    const lastWheelAt = useRef(0);

    useEffect(() => {
        if (profiles.length > 0 && !isLoading && hasMore && cursor + itemsPerScreen >= profiles.length) {
            loadMore();
        }
    }, [profiles.length, cursor, itemsPerScreen, hasMore, isLoading, loadMore]);

    useEffect(() => {
        function handleWheel(event: WheelEvent) {
            if (event.deltaY <= 0) return;

            const now = Date.now();
            if (now - lastWheelAt.current < WHEEL_COOLDOWN_MS) return;

            const wouldExceedBuffer = cursor + itemsPerScreen >= profiles.length;
            if (wouldExceedBuffer && (isLoading || !hasMore)) return;

            lastWheelAt.current = now;
            advance(itemsPerScreen);
        }

        window.addEventListener("wheel", handleWheel);
        return () => window.removeEventListener("wheel", handleWheel);
    }, [cursor, itemsPerScreen, profiles.length, hasMore, isLoading, advance]);

    const batch = profiles.slice(cursor, cursor + itemsPerScreen);

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
                {batch.map((profile) => (
                    <ProfileCard key={profile.id} profile={profile} />
                ))}
            </div>
        </div>
    );
}
