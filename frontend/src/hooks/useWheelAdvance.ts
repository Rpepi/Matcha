import { useEffect, useRef } from "react";
import { transitionDurationMs } from "@/lib/browseAnimation";

interface UseWheelAdvanceParams {
    batchSize: number;
    advance: () => void;
}

export function useWheelAdvance({ batchSize, advance }: UseWheelAdvanceParams) {
    const lastWheelAt = useRef(0);

    useEffect(() => {
        function handleWheel(event: WheelEvent) {
            if (event.deltaY <= 0) return;

            const now = Date.now();
            if (now - lastWheelAt.current < transitionDurationMs(batchSize)) return;

            lastWheelAt.current = now;
            advance();
        }

        window.addEventListener("wheel", handleWheel);
        return () => window.removeEventListener("wheel", handleWheel);
    }, [batchSize, advance]);
}
