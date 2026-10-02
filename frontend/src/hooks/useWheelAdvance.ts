import { useEffect, useRef } from "react";
import { transitionDurationMs } from "@/lib/browseAnimation";

interface UseWheelAdvanceParams {
    cursor: number;
    itemsPerScreen: number;
    bufferedCount: number;
    batchSize: number;
    hasMore: boolean;
    isLoading: boolean;
    advance: (itemsPerScreen: number) => void;
}

export function useWheelAdvance({
    cursor,
    itemsPerScreen,
    bufferedCount,
    batchSize,
    hasMore,
    isLoading,
    advance,
}: UseWheelAdvanceParams) {
    const lastWheelAt = useRef(0);

    useEffect(() => {
        function handleWheel(event: WheelEvent) {
            if (event.deltaY <= 0) return;

            const now = Date.now();
            if (now - lastWheelAt.current < transitionDurationMs(batchSize)) return;

            const wouldExceedBuffer = cursor + itemsPerScreen >= bufferedCount;
            if (wouldExceedBuffer && (isLoading || !hasMore)) return;

            lastWheelAt.current = now;
            advance(itemsPerScreen);
        }

        window.addEventListener("wheel", handleWheel);
        return () => window.removeEventListener("wheel", handleWheel);
    }, [cursor, itemsPerScreen, bufferedCount, batchSize, hasMore, isLoading, advance]);
}
