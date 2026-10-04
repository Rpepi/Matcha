import { useEffect, useLayoutEffect, useRef, useState } from "react";
import { ArrowDown, Loader2 } from "lucide-react";
import type { ChatMessage } from "@/api/chat";
import { dayKey, formatDayLabel, formatMessageTime, parseServerDate } from "@/lib/chatTime";

const GROUP_GAP_MS = 5 * 60 * 1000;
const LOAD_OLDER_THRESHOLD_PX = 120;
const STICK_TO_BOTTOM_PX = 80;

interface MessageListProps {
    messages: ChatMessage[];
    myId: number;
    partnerName: string;
    hasMore: boolean;
    isLoadingOlder: boolean;
    olderError: boolean;
    onLoadOlder: () => void;
}

function gapMs(a: ChatMessage, b: ChatMessage): number {
    return parseServerDate(b.created_at).getTime() - parseServerDate(a.created_at).getTime();
}

export default function MessageList({
    messages,
    myId,
    partnerName,
    hasMore,
    isLoadingOlder,
    olderError,
    onLoadOlder,
}: MessageListProps) {
    const containerRef = useRef<HTMLDivElement>(null);
    const stickToBottom = useRef(true);
    const heightAfterLastLayout = useRef(0);
    const firstId = useRef<number | null>(null);
    const lastId = useRef<number | null>(null);
    const [hasNewBelow, setHasNewBelow] = useState(false);

    // Keeps the viewport where the reader is: first paint and own messages go
    // to the bottom, older pages are inserted above without moving the text
    // being read, and a message arriving while reading history is announced
    // instead of yanking the scroll.
    useLayoutEffect(() => {
        const el = containerRef.current;
        if (!el || messages.length === 0) return;

        const newFirst = messages[0].id;
        const newest = messages[messages.length - 1];

        if (firstId.current === null || lastId.current === null) {
            el.scrollTop = el.scrollHeight;
        } else {
            if (newFirst < firstId.current) {
                el.scrollTop += el.scrollHeight - heightAfterLastLayout.current;
            }
            if (newest.id > lastId.current) {
                if (stickToBottom.current || newest.sender_id === myId) {
                    el.scrollTop = el.scrollHeight;
                } else {
                    setHasNewBelow(true);
                }
            }
        }

        firstId.current = newFirst;
        lastId.current = newest.id;
        heightAfterLastLayout.current = el.scrollHeight;
    }, [messages, myId]);

    // A short conversation that does not fill the screen never scrolls, so
    // nothing would ask for the earlier messages: keep loading until it does.
    useEffect(() => {
        const el = containerRef.current;
        if (!el || messages.length === 0 || !hasMore || isLoadingOlder || olderError) return;
        if (el.scrollHeight <= el.clientHeight) onLoadOlder();
    }, [messages, hasMore, isLoadingOlder, olderError, onLoadOlder]);

    function handleScroll() {
        const el = containerRef.current;
        if (!el) return;

        const distanceFromBottom = el.scrollHeight - el.scrollTop - el.clientHeight;
        stickToBottom.current = distanceFromBottom < STICK_TO_BOTTOM_PX;
        if (stickToBottom.current) setHasNewBelow(false);

        if (el.scrollTop < LOAD_OLDER_THRESHOLD_PX && hasMore && !isLoadingOlder && !olderError) onLoadOlder();
    }

    function scrollToBottom() {
        const el = containerRef.current;
        if (el) el.scrollTo({ top: el.scrollHeight, behavior: "smooth" });
    }

    return (
        <div className="relative min-h-0 flex-1">
            <div
                ref={containerRef}
                onScroll={handleScroll}
                role="log"
                aria-label={`Conversation with ${partnerName}`}
                className="flex h-full flex-col overflow-y-auto px-4 py-4 md:px-6"
                // Scroll position is managed above; the browser's own anchoring would apply the correction twice.
                style={{ overflowAnchor: "none" }}
            >
                <div className="mt-auto flex flex-col">
                    {!hasMore && (
                        <p className="mb-4 text-center text-xs text-grey">
                            This is the start of your conversation with {partnerName}.
                        </p>
                    )}

                    {messages.map((message, i) => {
                        const previous = messages[i - 1];
                        const next = messages[i + 1];
                        const mine = message.sender_id === myId;

                        const newDay = !previous || dayKey(previous.created_at) !== dayKey(message.created_at);
                        const startsGroup =
                            newDay || previous.sender_id !== message.sender_id || gapMs(previous, message) > GROUP_GAP_MS;
                        const endsGroup =
                            !next ||
                            next.sender_id !== message.sender_id ||
                            dayKey(next.created_at) !== dayKey(message.created_at) ||
                            gapMs(message, next) > GROUP_GAP_MS;

                        return (
                            <div key={message.id} className="flex flex-col">
                                {newDay && (
                                    <div className="my-4 flex items-center gap-3 text-xs font-medium text-grey">
                                        <span className="h-px flex-1 bg-grey/20" />
                                        {formatDayLabel(message.created_at)}
                                        <span className="h-px flex-1 bg-grey/20" />
                                    </div>
                                )}
                                <div
                                    className={`flex flex-col ${mine ? "items-end" : "items-start"} ${
                                        startsGroup && !newDay ? "mt-3" : "mt-0.5"
                                    }`}
                                >
                                    <p
                                        className={`max-w-[80%] rounded-3xl px-4 py-2 text-[15px] leading-snug break-words whitespace-pre-wrap text-ink md:max-w-[65%] ${
                                            mine ? "bg-matcha" : "bg-grey/15"
                                        } ${endsGroup ? (mine ? "rounded-br-md" : "rounded-bl-md") : ""}`}
                                    >
                                        {message.content}
                                    </p>
                                    {endsGroup && (
                                        <span className="mt-1 px-1 text-[11px] text-grey">
                                            {formatMessageTime(message.created_at)}
                                        </span>
                                    )}
                                </div>
                            </div>
                        );
                    })}
                </div>
            </div>

            {(isLoadingOlder || olderError) && (
                <div className="pointer-events-none absolute inset-x-0 top-3 flex justify-center">
                    {isLoadingOlder ? (
                        <span
                            role="status"
                            className="flex items-center gap-2 rounded-full bg-paper px-3 py-1.5 text-xs text-grey shadow-md shadow-ink/10"
                        >
                            <Loader2 className="h-3.5 w-3.5 animate-spin text-matcha" />
                            Loading earlier messages
                        </span>
                    ) : (
                        <button
                            type="button"
                            onClick={onLoadOlder}
                            className="pointer-events-auto cursor-pointer rounded-full bg-paper px-3 py-1.5 text-xs font-medium text-ink shadow-md shadow-ink/10 transition hover:bg-matcha/25"
                        >
                            Couldn't load earlier messages. Retry
                        </button>
                    )}
                </div>
            )}

            {hasNewBelow && (
                <div className="pointer-events-none absolute inset-x-0 bottom-3 flex justify-center">
                    <button
                        type="button"
                        onClick={scrollToBottom}
                        className="pointer-events-auto flex cursor-pointer items-center gap-1.5 rounded-full bg-ink px-4 py-2 text-xs font-medium text-paper shadow-lg shadow-ink/20 transition hover:bg-ink/90"
                    >
                        <ArrowDown className="h-3.5 w-3.5" />
                        New messages
                    </button>
                </div>
            )}
        </div>
    );
}
