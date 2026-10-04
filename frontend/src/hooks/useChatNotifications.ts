import { useEffect, useRef } from "react";

/** Notification types that change what the chat screens show. `like` and `visit` do not. */
const CHAT_RELEVANT = new Set(["message", "match", "unlike"]);

/**
 * Listens to the server's SSE stream while `enabled`. `onEvent(type, fromUserId)`
 * fires for each chat-relevant notification; the payload only carries
 * `{type, from_user_id}`, never message content, so it is a signal to refresh,
 * not something to display. `onReconnect` fires when the stream comes back
 * after a drop: events sent meanwhile are not replayed, so the caller should refresh.
 */
export function useChatNotifications(
    enabled: boolean,
    onEvent: (type: string, fromUserId: number) => void,
    onReconnect: () => void,
) {
    const handlers = useRef({ onEvent, onReconnect });

    useEffect(() => {
        handlers.current = { onEvent, onReconnect };
    });

    useEffect(() => {
        if (!enabled) return;

        const source = new EventSource("/api/notifications/stream", { withCredentials: true });
        let hasOpened = false;

        source.onopen = () => {
            if (hasOpened) handlers.current.onReconnect();
            hasOpened = true;
        };

        source.onmessage = (event) => {
            try {
                const data = JSON.parse(event.data);
                const from = Number(data?.from_user_id);
                if (CHAT_RELEVANT.has(data?.type) && Number.isInteger(from)) handlers.current.onEvent(data.type, from);
            } catch {
                // Not a notification we understand: ignore it.
            }
        };

        return () => source.close();
    }, [enabled]);
}
