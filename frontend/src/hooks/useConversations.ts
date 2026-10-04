import { useCallback, useEffect, useRef, useState } from "react";
import { getConversations, type ChatMessage, type Conversation } from "@/api/chat";

const LOAD_ERROR = "Could not load your conversations. Please try again.";

/** `enabled` is false while nobody is signed in: nothing is fetched and any previous user's data is dropped. */
export function useConversations(enabled: boolean) {
    const [conversations, setConversations] = useState<Conversation[]>([]);
    const [isLoading, setIsLoading] = useState(true);
    const [error, setError] = useState<string | null>(null);
    const latestRequest = useRef(0);

    // True once a fetch has succeeded: only then is a stale list worth keeping over an error.
    const hasLoaded = useRef(false);

    /**
     * `silent` refreshes keep the list on screen and swallow failures: a stale
     * list is better than an error screen replacing a working one. A request
     * that replaces an earlier one (a silent refresh landing while the first
     * load is still in flight) inherits its job: when it ends, loading ends.
     */
    const reload = useCallback(async ({ silent = false }: { silent?: boolean } = {}) => {
        const requestId = ++latestRequest.current;
        if (!silent) {
            setIsLoading(true);
            setError(null);
        }

        try {
            const response = await getConversations();
            if (!response.ok) {
                const data = await response.json().catch(() => null);
                throw new Error(typeof data?.detail === "string" ? data.detail : LOAD_ERROR);
            }
            const data = (await response.json()) as Conversation[];
            if (requestId !== latestRequest.current) return;
            hasLoaded.current = true;
            setConversations(data);
            setError(null);
        } catch (err) {
            if (requestId !== latestRequest.current) return;
            if (silent && hasLoaded.current) return;
            setError(err instanceof Error ? err.message : LOAD_ERROR);
        } finally {
            if (requestId === latestRequest.current) setIsLoading(false);
        }
    }, []);

    useEffect(() => {
        if (!enabled) {
            latestRequest.current += 1; // drop anything still in flight
            hasLoaded.current = false;
            setConversations([]);
            setError(null);
            setIsLoading(true);
            return;
        }
        void reload();
        return () => {
            latestRequest.current += 1;
        };
    }, [enabled, reload]);

    /** New last message for a conversation: moves it to the top and counts it as unread if needed. */
    const applyMessage = useCallback((userId: number, message: ChatMessage, { countUnread }: { countUnread: boolean }) => {
        setConversations((prev) => {
            const index = prev.findIndex((c) => c.user.id === userId);
            if (index === -1) return prev;
            const current = prev[index];
            if (current.last_message && current.last_message.id >= message.id) return prev;

            const updated: Conversation = {
                ...current,
                last_message: message,
                unread_count: countUnread ? current.unread_count + 1 : current.unread_count,
            };
            return [updated, ...prev.slice(0, index), ...prev.slice(index + 1)];
        });
    }, []);

    const clearUnread = useCallback((userId: number) => {
        setConversations((prev) =>
            prev.some((c) => c.user.id === userId && c.unread_count > 0)
                ? prev.map((c) => (c.user.id === userId ? { ...c, unread_count: 0 } : c))
                : prev,
        );
    }, []);

    return { conversations, isLoading, error, reload, applyMessage, clearUnread };
}
