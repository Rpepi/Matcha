import { Link } from "react-router-dom";
import { Loader2, MessageCircle } from "lucide-react";
import type { Conversation } from "@/api/chat";
import { formatListTime } from "@/lib/chatTime";
import Avatar from "./Avatar";

interface ConversationListProps {
    conversations: Conversation[];
    myId: number;
    activeId: number | null;
    isLoading: boolean;
    error: string | null;
    onRetry: () => void;
}

function ConversationItem({ conversation, myId, active }: { conversation: Conversation; myId: number; active: boolean }) {
    const { user, last_message: last, unread_count: unread } = conversation;
    const hasUnread = unread > 0;
    const preview = last ? `${last.sender_id === myId ? "You: " : ""}${last.content}` : "No messages yet. Say hi!";

    return (
        <Link
            to={`/chat/${user.id}`}
            aria-current={active ? "page" : undefined}
            className={`flex items-center gap-3 rounded-2xl px-3 py-3 transition hover:bg-matcha/25 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-[-2px] focus-visible:outline-matcha ${
                active ? "bg-grey/10" : ""
            }`}
        >
            <Avatar user={user} size={52} showStatus />

            <div className="min-w-0 flex-1">
                <div className="flex items-baseline justify-between gap-2">
                    <span className={`truncate text-[15px] text-ink ${hasUnread ? "font-bold" : "font-medium"}`}>
                        {user.first_name}
                    </span>
                    {last && <span className="shrink-0 text-xs text-grey">{formatListTime(last.created_at)}</span>}
                </div>

                <div className="flex items-center justify-between gap-2">
                    <span className={`truncate text-sm ${hasUnread ? "font-medium text-ink" : "text-grey"}`}>
                        {preview}
                    </span>
                    {hasUnread && (
                        <span className="flex h-5 min-w-5 shrink-0 items-center justify-center rounded-full bg-matcha px-1.5 text-xs font-bold text-ink">
                            {unread > 99 ? "99+" : unread}
                            <span className="sr-only"> unread messages</span>
                        </span>
                    )}
                </div>
            </div>
        </Link>
    );
}

export default function ConversationList({ conversations, myId, activeId, isLoading, error, onRetry }: ConversationListProps) {
    if (isLoading) {
        return (
            <div className="flex flex-1 items-center justify-center">
                <Loader2 className="h-6 w-6 animate-spin text-matcha" />
            </div>
        );
    }

    if (error) {
        return (
            <div className="flex flex-1 flex-col items-center justify-center gap-3 p-6 text-center">
                <p className="text-sm text-grey">{error}</p>
                <button
                    type="button"
                    onClick={onRetry}
                    className="cursor-pointer rounded-full bg-grey/10 px-5 py-2 text-sm font-medium text-ink transition hover:bg-matcha/25"
                >
                    Try again
                </button>
            </div>
        );
    }

    if (conversations.length === 0) {
        return (
            <div className="flex flex-1 flex-col items-center justify-center gap-3 p-8 text-center">
                <span className="flex h-14 w-14 items-center justify-center rounded-full bg-matcha/25">
                    <MessageCircle className="h-7 w-7 text-ink" />
                </span>
                <p className="font-display text-lg text-ink">No conversations yet</p>
                <p className="text-sm text-grey">When you and someone like each other, you can chat here.</p>
                <Link
                    to="/browse"
                    className="rounded-full bg-matcha px-5 py-2 text-sm font-medium text-ink transition hover:brightness-95"
                >
                    Find people
                </Link>
            </div>
        );
    }

    return (
        <nav aria-label="Conversations" className="min-h-0 flex-1 overflow-y-auto px-2 pb-2">
            <ul className="flex flex-col gap-0.5">
                {conversations.map((conversation) => (
                    <li key={conversation.user.id}>
                        <ConversationItem
                            conversation={conversation}
                            myId={myId}
                            active={conversation.user.id === activeId}
                        />
                    </li>
                ))}
            </ul>
        </nav>
    );
}
