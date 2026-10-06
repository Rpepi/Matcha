import { useEffect, useRef, type MutableRefObject } from "react";

interface Handlers {
    onEvent: (type: string, fromUserId: number) => void;
    onReconnect: () => void;
}

interface Subscriber {
    relevant: Set<string>;
    handlers: MutableRefObject<Handlers>;
}

// One connection for the whole tab, shared by everyone who listens (the chat, the
// notification bell): each connection costs the server a Redis subscription, and two
// of them would deliver every event twice. Subscribers come and go with their
// components; the connection lives as long as at least one is subscribed.
const subscribers = new Set<Subscriber>();
let source: EventSource | null = null;
let hasOpened = false;
let closeTimer: number | undefined;

function connect() {
    if (source) return;

    source = new EventSource("/api/notifications/stream", { withCredentials: true });
    hasOpened = false;

    source.onopen = () => {
        if (hasOpened) subscribers.forEach((s) => s.handlers.current.onReconnect());
        hasOpened = true;
    };

    source.onmessage = (event) => {
        try {
            const data = JSON.parse(event.data);
            const from = Number(data?.from_user_id);
            if (!Number.isInteger(from)) return;
            subscribers.forEach((s) => {
                if (s.relevant.has(data?.type)) s.handlers.current.onEvent(data.type, from);
            });
        } catch {
            // Not a notification we understand: ignore it.
        }
    };
}

function disconnectIfUnused() {
    if (subscribers.size > 0 || !source) return;
    source.close();
    source = null;
}

/**
 * Listens to the server's SSE stream while `enabled`. `onEvent(type, fromUserId)`
 * fires for each notification whose type is in `relevant`; the payload only carries
 * `{type, from_user_id}`, never message content, so it is a signal to refresh,
 * not something to display. `onReconnect` fires when the stream comes back
 * after a drop: events sent meanwhile are not replayed, so the caller should refresh.
 *
 * `relevant` must be a stable value (a constant at module level): it is a dependency
 * of the effect.
 */
export function useNotificationStream(
    enabled: boolean,
    relevant: Set<string>,
    onEvent: (type: string, fromUserId: number) => void,
    onReconnect: () => void,
) {
    const handlers = useRef({ onEvent, onReconnect });

    useEffect(() => {
        handlers.current = { onEvent, onReconnect };
    });

    useEffect(() => {
        if (!enabled) return;

        const subscriber: Subscriber = { relevant, handlers };
        subscribers.add(subscriber);
        window.clearTimeout(closeTimer);
        connect();

        return () => {
            subscribers.delete(subscriber);
            // Deferred: in development React unmounts and remounts effects at once, and
            // closing right away would drop the connection only to reopen it.
            closeTimer = window.setTimeout(disconnectIfUnused, 0);
        };
    }, [enabled, relevant]);
}
