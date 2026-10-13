import { useCallback, useEffect, useRef } from "react";
import { transitionDurationMs } from "@/lib/browseAnimation";

// A shorter move is a tap (opening a profile), not a swipe.
const SWIPE_MIN_PX = 40;

// true: next profiles, false: the previous ones
const KEYS: Record<string, boolean> = {
    ArrowRight: true,
    ArrowDown: true,
    PageDown: true,
    ArrowLeft: false,
    ArrowUp: false,
    PageUp: false,
};

interface UseBrowseNavigationParams {
    batchSize: number;
    advance: () => void;
    goBack: () => void;
}

// Events from the filters dialog or a form field belong to them: scrolling the
// dialog or dragging a slider must not move the cards behind it.
function belongsElsewhere(target: EventTarget | null): boolean {
    return (
        target instanceof Element &&
        target.closest('[role="dialog"], input, textarea, select, [role="slider"], [contenteditable="true"]') !== null
    );
}

/**
 * Moves through the profiles one screen at a time, whatever the device: the
 * mouse wheel, a swipe on a touch screen (a phone has no wheel), the arrow
 * keys, or the returned `next` / `previous` for buttons. Down, a finger moving
 * left or up, and the right/down arrows go forward; the opposite goes back.
 * At most one move per card transition, so a long scroll or a quick swipe never
 * skips a screen.
 */
export function useBrowseNavigation({ batchSize, advance, goBack }: UseBrowseNavigationParams) {
    const lastMoveAt = useRef(0);
    // Read when a move happens, so the listeners below are added once
    const latest = useRef({ batchSize, advance, goBack });
    useEffect(() => {
        latest.current = { batchSize, advance, goBack };
    });

    const move = useCallback((forward: boolean) => {
        const now = Date.now();
        if (now - lastMoveAt.current < transitionDurationMs(latest.current.batchSize)) return;
        lastMoveAt.current = now;
        if (forward) latest.current.advance();
        else latest.current.goBack();
    }, []);

    useEffect(() => {
        function handleWheel(event: WheelEvent) {
            if (event.deltaY === 0 || belongsElsewhere(event.target)) return;
            move(event.deltaY > 0);
        }

        let touchStart: { x: number; y: number } | null = null;
        function handleTouchStart(event: TouchEvent) {
            touchStart =
                event.touches.length === 1 && !belongsElsewhere(event.target)
                    ? { x: event.touches[0].clientX, y: event.touches[0].clientY }
                    : null;
        }
        function handleTouchEnd(event: TouchEvent) {
            if (!touchStart) return;
            const touch = event.changedTouches[0];
            const dx = touch.clientX - touchStart.x;
            const dy = touch.clientY - touchStart.y;
            touchStart = null;
            const distance = Math.abs(dx) >= Math.abs(dy) ? dx : dy;
            if (Math.abs(distance) < SWIPE_MIN_PX) return;
            move(distance < 0);
        }

        function handleKeyDown(event: KeyboardEvent) {
            if (!(event.key in KEYS) || event.altKey || event.ctrlKey || event.metaKey) return;
            if (belongsElsewhere(event.target)) return;
            event.preventDefault();
            move(KEYS[event.key]);
        }

        window.addEventListener("wheel", handleWheel);
        window.addEventListener("touchstart", handleTouchStart, { passive: true });
        window.addEventListener("touchend", handleTouchEnd);
        window.addEventListener("keydown", handleKeyDown);
        return () => {
            window.removeEventListener("wheel", handleWheel);
            window.removeEventListener("touchstart", handleTouchStart);
            window.removeEventListener("touchend", handleTouchEnd);
            window.removeEventListener("keydown", handleKeyDown);
        };
    }, [move]);

    const next = useCallback(() => move(true), [move]);
    const previous = useCallback(() => move(false), [move]);
    return { next, previous };
}
