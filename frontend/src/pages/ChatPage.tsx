import { useCallback, useEffect, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { Loader2, MessageCircle } from "lucide-react";
import { useProfileContext } from "@/context/ProfileContext";
import { useToast } from "@/context/ToastContext";
import { useChatContext } from "@/context/ChatContext";
import { useNotificationContext } from "@/context/NotificationContext";
import ChatThread from "@/components/chat/ChatThread";
import ConversationList from "@/components/chat/ConversationList";
import type { ChatMessage } from "@/api/chat";

const MAX_USER_ID = 2 ** 31 - 1;

/** `/chat/:id` as a user id, or null when the segment cannot be one. */
function parseUserId(raw: string | undefined): number | null {
    if (raw === undefined || !/^\d{1,10}$/.test(raw)) return null;
    const id = Number(raw);
    return id >= 1 && id <= MAX_USER_ID ? id : null;
}

export default function ChatPage() {
    const { id: rawId } = useParams<{ id: string }>();
    const navigate = useNavigate();
    const { profile } = useProfileContext();
    const { showNotice } = useToast();
    const { conversations, isLoading, error, reload, applyMessage, clearUnread, setActiveChatId } = useChatContext();
    const { refreshUnreadCount } = useNotificationContext();
    const [isFresh, setIsFresh] = useState(false);

    const myId = profile?.id ?? 0;
    const activeId = parseUserId(rawId);
    const active = conversations.find((c) => c.user.id === activeId) ?? null;
    const hasThreadOpen = rawId !== undefined;

    // The shared list may predate a match made moments ago (a "Message" link
    // clicked right after matching): refresh before deciding a conversation does not exist.
    useEffect(() => {
        let cancelled = false;
        void reload({ silent: true }).then(() => {
            if (!cancelled) setIsFresh(true);
        });
        return () => {
            cancelled = true;
        };
    }, [reload]);

    useEffect(() => {
        setActiveChatId(activeId);
        return () => setActiveChatId(null);
    }, [activeId, setActiveChatId]);

    // Unknown, unmatched or malformed id once the list is known.
    useEffect(() => {
        if (!hasThreadOpen || isLoading || error || !isFresh || active) return;
        showNotice("That conversation isn't available.");
        navigate("/chat", { replace: true });
    }, [hasThreadOpen, isLoading, error, isFresh, active, showNotice, navigate]);

    const handleMessage = useCallback(
        (message: ChatMessage) => {
            if (activeId === null) return;
            // Unread only if it arrives while nobody is looking: a visible thread marks it seen at once.
            const unseen = message.sender_id !== myId && document.visibilityState !== "visible";
            applyMessage(activeId, message, { countUnread: unseen });
        },
        [activeId, myId, applyMessage],
    );

    const handleSeen = useCallback(() => {
        if (activeId !== null) clearUnread(activeId);
        // The server also marked that conversation's "message" notification as read.
        void refreshUnreadCount();
    }, [activeId, clearUnread, refreshUnreadCount]);

    const handleBlocked = useCallback(() => {
        navigate("/chat", { replace: true });
        void reload({ silent: true });
    }, [navigate, reload]);

    const name = active?.user.first_name;
    const handleDenied = useCallback(() => {
        showNotice(name ? `You're no longer matched with ${name}.` : "That conversation isn't available.");
        navigate("/chat", { replace: true });
        void reload({ silent: true });
    }, [name, showNotice, navigate, reload]);

    return (
        <div className="flex h-[calc(100dvh-5rem)] md:h-dvh">
            <aside
                className={`${hasThreadOpen ? "hidden md:flex" : "flex"} w-full shrink-0 flex-col border-grey/15 md:w-80 md:border-r-3 lg:w-96`}
            >
                <h1 className="px-6 pt-6 pb-4 font-display text-3xl text-ink">Messages</h1>
                <ConversationList
                    conversations={conversations}
                    myId={myId}
                    activeId={activeId}
                    isLoading={isLoading}
                    error={error}
                    onRetry={() => void reload()}
                />
            </aside>

            <section className={`${hasThreadOpen ? "flex" : "hidden md:flex"} min-w-0 flex-1 flex-col`}>
                {active ? (
                    <ChatThread
                        key={active.user.id}
                        conversation={active}
                        myId={myId}
                        onMessage={handleMessage}
                        onSeen={handleSeen}
                        onDenied={handleDenied}
                        onBlocked={handleBlocked}
                    />
                ) : hasThreadOpen ? (
                    <div className="flex flex-1 items-center justify-center">
                        <Loader2 className="h-6 w-6 animate-spin text-matcha" />
                    </div>
                ) : (
                    <div className="flex flex-1 flex-col items-center justify-center gap-3 p-8 text-center">
                        <span className="flex h-16 w-16 items-center justify-center rounded-full bg-matcha/25">
                            <MessageCircle className="h-8 w-8 text-ink" />
                        </span>
                        <p className="font-display text-xl text-ink">Your messages</p>
                        <p className="max-w-xs text-sm text-grey">Pick a conversation to read it and reply.</p>
                    </div>
                )}
            </section>
        </div>
    );
}
