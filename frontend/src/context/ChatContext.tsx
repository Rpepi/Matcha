import { createContext, useCallback, useContext, useEffect, useMemo, useRef, type ReactNode } from "react";
import { useProfileContext } from "@/context/ProfileContext";
import { useChatNotifications } from "@/hooks/useChatNotifications";
import { useConversations } from "@/hooks/useConversations";

const REFRESH_DEBOUNCE_MS = 400;

type ConversationsState = ReturnType<typeof useConversations>;

interface ChatContextValue extends ConversationsState {
    /** Unread messages across all conversations: what the sidebar badge shows. */
    unreadTotal: number;
    /** The conversation currently open on screen, so its own socket handles its messages. */
    setActiveChatId: (id: number | null) => void;
}

const ChatContext = createContext<ChatContextValue | undefined>(undefined);

/**
 * Owns the conversation list for the whole signed-in app, not just the chat
 * page, so the sidebar badge is right on every page and the chat page opens
 * with its list already there.
 */
export function ChatProvider({ children }: { children: ReactNode }) {
    const { status } = useProfileContext();
    const enabled = status === "complete";
    const conversations = useConversations(enabled);
    const { reload } = conversations;

    const activeChatId = useRef<number | null>(null);
    const setActiveChatId = useCallback((id: number | null) => {
        activeChatId.current = id;
    }, []);

    // Debounced: a burst of notifications is one fetch.
    const refreshTimer = useRef<number | undefined>(undefined);
    const scheduleRefresh = useCallback(() => {
        window.clearTimeout(refreshTimer.current);
        refreshTimer.current = window.setTimeout(() => void reload({ silent: true }), REFRESH_DEBOUNCE_MS);
    }, [reload]);
    useEffect(() => () => window.clearTimeout(refreshTimer.current), []);

    useChatNotifications(
        enabled,
        (type, fromUserId) => {
            // The open conversation already gets its messages through its own socket.
            if (type === "message" && fromUserId === activeChatId.current) return;
            scheduleRefresh();
        },
        scheduleRefresh,
    );

    // Back on a tab that sat in the background: whatever happened meanwhile may have been missed.
    useEffect(() => {
        if (!enabled) return;
        const onVisible = () => {
            if (document.visibilityState === "visible") scheduleRefresh();
        };
        document.addEventListener("visibilitychange", onVisible);
        return () => document.removeEventListener("visibilitychange", onVisible);
    }, [enabled, scheduleRefresh]);

    const { conversations: list, isLoading, error, applyMessage, clearUnread } = conversations;
    const unreadTotal = useMemo(() => list.reduce((total, c) => total + c.unread_count, 0), [list]);

    // Memoized: a new object on every render would re-render every consumer
    // (sidebar, chat page) each time the provider does, even if nothing changed.
    const value = useMemo(
        () => ({ conversations: list, isLoading, error, reload, applyMessage, clearUnread, unreadTotal, setActiveChatId }),
        [list, isLoading, error, reload, applyMessage, clearUnread, unreadTotal, setActiveChatId],
    );

    return <ChatContext.Provider value={value}>{children}</ChatContext.Provider>;
}

export function useChatContext(): ChatContextValue {
    const ctx = useContext(ChatContext);
    if (!ctx) throw new Error("useChatContext must be used within a ChatProvider");
    return ctx;
}
