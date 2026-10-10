import { useCallback, useEffect, useState, type ReactNode } from "react";
import { Link, useLocation, useNavigate, useParams } from "react-router-dom";
import { Eye, Heart, Loader2, MessageCircle } from "lucide-react";
import { useProfileContext } from "@/context/ProfileContext";
import { useToast } from "@/context/ToastContext";
import { useChatContext } from "@/context/ChatContext";
import { useNotificationContext } from "@/context/NotificationContext";
import ChatThread from "@/components/chat/ChatThread";
import ConversationList from "@/components/chat/ConversationList";
import VisitorsList from "@/components/chat/VisitorsList";
import LikesList from "@/components/chat/LikesList";
import type { ChatMessage } from "@/api/chat";

const MAX_USER_ID = 2 ** 31 - 1;

type Tab = "messages" | "visitors" | "likes";

const TABS: { tab: Tab; to: string; label: string }[] = [
    { tab: "messages", to: "/chat", label: "Messages" },
    { tab: "visitors", to: "/chat/visitors", label: "Visitors" },
    { tab: "likes", to: "/chat/likes", label: "Likes" },
];

const EMPTY_STATE: Record<Tab, { icon: ReactNode; title: string; text: string }> = {
    messages: {
        icon: <MessageCircle className="h-8 w-8 text-ink" />,
        title: "Your messages",
        text: "Pick a conversation to read it and reply.",
    },
    visitors: {
        icon: <Eye className="h-8 w-8 text-ink" />,
        title: "Your visitors",
        text: "Select someone to view their profile.",
    },
    likes: {
        icon: <Heart className="h-8 w-8 text-ink" />,
        title: "Your likes",
        text: "Select someone to view their profile.",
    },
};

function TabBar({ activeTab }: { activeTab: Tab }) {
    return (
        <div className="mx-6 mt-6 mb-4 flex gap-1 rounded-full bg-grey/10 p-1">
            {TABS.map(({ tab, to, label }) => (
                <Link
                    key={tab}
                    to={to}
                    aria-current={activeTab === tab ? "page" : undefined}
                    className={`flex-1 rounded-full px-3 py-1.5 text-center text-sm font-medium transition ${
                        activeTab === tab ? "bg-paper text-ink shadow-sm" : "text-grey hover:text-ink"
                    }`}
                >
                    {label}
                </Link>
            ))}
        </div>
    );
}

/** `/chat/:id` as a user id, or null when the segment cannot be one. */
function parseUserId(raw: string | undefined): number | null {
    if (raw === undefined || !/^\d{1,10}$/.test(raw)) return null;
    const id = Number(raw);
    return id >= 1 && id <= MAX_USER_ID ? id : null;
}

export default function ChatPage() {
    const { id: rawId } = useParams<{ id: string }>();
    const location = useLocation();
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
    const activeTab: Tab = location.pathname === "/chat/visitors" ? "visitors" : location.pathname === "/chat/likes" ? "likes" : "messages";

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
                <TabBar activeTab={activeTab} />
                {activeTab === "messages" ? (
                    <ConversationList
                        conversations={conversations}
                        myId={myId}
                        activeId={activeId}
                        isLoading={isLoading}
                        error={error}
                        onRetry={() => void reload()}
                    />
                ) : activeTab === "visitors" ? (
                    <VisitorsList />
                ) : (
                    <LikesList />
                )}
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
                            {EMPTY_STATE[activeTab].icon}
                        </span>
                        <p className="font-display text-xl text-ink">{EMPTY_STATE[activeTab].title}</p>
                        <p className="max-w-xs text-sm text-grey">{EMPTY_STATE[activeTab].text}</p>
                    </div>
                )}
            </section>
        </div>
    );
}
