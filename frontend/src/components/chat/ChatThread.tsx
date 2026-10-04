import { useRef, useState } from "react";
import { Link } from "react-router-dom";
import { ArrowLeft, Loader2 } from "lucide-react";
import type { ChatMessage, Conversation } from "@/api/chat";
import BlockButton from "@/components/BlockButton";
import { useToast } from "@/context/ToastContext";
import { useBlock } from "@/hooks/useBlock";
import { useChat } from "@/hooks/useChat";
import { formatLastSeen } from "@/lib/chatTime";
import Avatar from "./Avatar";
import MessageComposer from "./MessageComposer";
import MessageList from "./MessageList";

interface ChatThreadProps {
    conversation: Conversation;
    myId: number;
    onMessage: (message: ChatMessage) => void;
    onSeen: () => void;
    onDenied: () => void;
    onBlocked: () => void;
}

const CONNECTION_LABEL = {
    connecting: "Connecting",
    reconnecting: "Connection lost. Reconnecting",
} as const;

/** Render with `key={user.id}`: every piece of state here belongs to one conversation. */
export default function ChatThread({ conversation, myId, onMessage, onSeen, onDenied, onBlocked }: ChatThreadProps) {
    const { user } = conversation;
    const { showError } = useToast();
    const [draft, setDraft] = useState("");

    // Blocking makes the server close this very socket; that must not also be
    // announced as "no longer matched", the block toast already says it.
    const blockStarted = useRef(false);
    const { block, isBlocking } = useBlock(user.id, user.first_name, onBlocked);
    async function handleBlock(): Promise<boolean> {
        blockStarted.current = true;
        const blocked = await block();
        if (!blocked) blockStarted.current = false;
        return blocked;
    }

    const chat = useChat({
        targetId: user.id,
        myId,
        initialUnread: conversation.unread_count,
        onMessage,
        onSeen,
        onDenied: () => {
            if (!blockStarted.current) onDenied();
        },
        // The server refused the message: put the text back unless the user already typed something else.
        onRejected: (content) => setDraft((current) => (current === "" ? content : current)),
    });

    function handleSubmit() {
        const content = draft.trim();
        if (!content) return;
        if (chat.send(content)) {
            setDraft("");
        } else {
            showError("You're not connected yet. Your message was not sent.");
        }
    }

    const connectionLabel =
        chat.connection === "connecting" || chat.connection === "reconnecting" ? CONNECTION_LABEL[chat.connection] : null;

    return (
        <div className="flex h-full min-h-0 flex-col">
            <header className="flex items-center gap-3 border-b-3 border-grey/15 px-3 py-3 md:px-6">
                <Link
                    to="/chat"
                    aria-label="Back to conversations"
                    className="rounded-full p-2 text-grey transition hover:bg-matcha/25 hover:text-ink md:hidden"
                >
                    <ArrowLeft className="h-6 w-6" />
                </Link>

                <Link
                    to={`/users/${user.id}`}
                    className="flex min-w-0 items-center gap-3 rounded-2xl pr-3 transition hover:opacity-80"
                >
                    <Avatar user={user} size={44} showStatus />
                    <span className="min-w-0">
                        <span className="block truncate font-display text-lg leading-tight text-ink">{user.first_name}</span>
                        <span className="block truncate text-xs text-grey">
                            {user.is_online ? "Active now" : formatLastSeen(user.last_seen)}
                        </span>
                    </span>
                </Link>

                <BlockButton
                    variant="icon"
                    name={user.first_name}
                    onConfirm={handleBlock}
                    isBlocking={isBlocking}
                    className="ml-auto"
                />
            </header>

            {connectionLabel && (
                <p
                    role="status"
                    className="flex items-center justify-center gap-2 bg-grey/10 px-4 py-1.5 text-xs text-grey"
                >
                    <Loader2 className="h-3.5 w-3.5 animate-spin" />
                    {connectionLabel}
                </p>
            )}

            {chat.historyState === "loading" && (
                <div className="flex flex-1 items-center justify-center">
                    <Loader2 className="h-6 w-6 animate-spin text-matcha" />
                </div>
            )}

            {chat.historyState === "error" && (
                <div className="flex flex-1 flex-col items-center justify-center gap-3 p-6 text-center">
                    <p className="text-sm text-grey">We couldn't load this conversation.</p>
                    <button
                        type="button"
                        onClick={chat.retryHistory}
                        className="cursor-pointer rounded-full bg-grey/10 px-5 py-2 text-sm font-medium text-ink transition hover:bg-matcha/25"
                    >
                        Try again
                    </button>
                </div>
            )}

            {chat.historyState === "ready" && chat.messages.length === 0 && (
                <div className="flex flex-1 flex-col items-center justify-center gap-2 p-6 text-center">
                    <Avatar user={user} size={88} />
                    <p className="mt-2 font-display text-xl text-ink">You matched with {user.first_name}</p>
                    <p className="text-sm text-grey">Say hi and break the ice.</p>
                </div>
            )}

            {chat.historyState === "ready" && chat.messages.length > 0 && (
                <MessageList
                    messages={chat.messages}
                    myId={myId}
                    partnerName={user.first_name}
                    hasMore={chat.hasMore}
                    isLoadingOlder={chat.isLoadingOlder}
                    olderError={chat.olderError}
                    onLoadOlder={chat.loadOlder}
                />
            )}

            <MessageComposer
                value={draft}
                onChange={setDraft}
                onSubmit={handleSubmit}
                isConnected={chat.connection === "open"}
                partnerName={user.first_name}
            />
        </div>
    );
}
