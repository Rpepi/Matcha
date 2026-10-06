import { useCallback, useEffect, useRef, useState } from "react";
import { chatSocketUrl, getMessages, markSeen, type ChatMessage, type MessagePage } from "@/api/chat";
import { useProfileContext } from "@/context/ProfileContext";
import { useToast } from "@/context/ToastContext";

export type ConnectionState = "connecting" | "open" | "reconnecting" | "denied";
export type HistoryState = "loading" | "ready" | "error";

const RETRY_BASE_MS = 1000;
const RETRY_MAX_MS = 15000;
const SEEN_DEBOUNCE_MS = 250;
const HISTORY_ERROR = "Could not load this conversation. Please try again.";

interface UseChatOptions {
    targetId: number;
    myId: number;
    /** Unread count when the conversation was opened: decides if history load must mark it seen. */
    initialUnread: number;
    onMessage: (message: ChatMessage) => void;
    onSeen: () => void;
    /** The match is gone (unlike / block) or the id is invalid. */
    onDenied: () => void;
    /** The server refused the last sent message (invalid, rate limited): give the text back. */
    onRejected: (content: string) => void;
}

type PageResult = { ok: true; page: MessagePage } | { ok: false; status: number; message: string };

async function fetchPage(targetId: number, before?: number, limit?: number): Promise<PageResult> {
    try {
        const response = await getMessages(targetId, { before, limit });
        if (!response.ok) {
            const data = await response.json().catch(() => null);
            const message = typeof data?.detail === "string" ? data.detail : HISTORY_ERROR;
            return { ok: false, status: response.status, message };
        }
        return { ok: true, page: (await response.json()) as MessagePage };
    } catch {
        return { ok: false, status: 0, message: "Network error. Check your connection and try again." };
    }
}

/** The API returns newest first; the screen wants oldest first. */
function toAscending(messages: ChatMessage[]): ChatMessage[] {
    return [...messages].reverse();
}

/** Union by id, oldest first: a message may arrive both live and in a history page. */
function mergeMessages(current: ChatMessage[], incoming: ChatMessage[]): ChatMessage[] {
    const byId = new Map<number, ChatMessage>();
    for (const message of current) byId.set(message.id, message);
    for (const message of incoming) byId.set(message.id, message);
    return [...byId.values()].sort((a, b) => a.id - b.id);
}

function isChatMessage(data: unknown): data is ChatMessage {
    if (typeof data !== "object" || data === null) return false;
    const m = data as Record<string, unknown>;
    return (
        typeof m.id === "number" &&
        typeof m.sender_id === "number" &&
        typeof m.content === "string" &&
        typeof m.created_at === "string"
    );
}

function isErrorFrame(data: unknown): data is { type: "error"; detail: string } {
    if (typeof data !== "object" || data === null) return false;
    const f = data as Record<string, unknown>;
    return f.type === "error" && typeof f.detail === "string";
}

export function useChat(options: UseChatOptions) {
    const { targetId, myId } = options;
    const { showError } = useToast();
    const { refetch: refetchProfile } = useProfileContext();

    // Callbacks change identity on every render; effects below must not
    // re-run (and reopen the socket) because of that, so they read the latest.
    const latest = useRef({ ...options, showError, refetchProfile });
    useEffect(() => {
        latest.current = { ...options, showError, refetchProfile };
    });

    const [messages, setMessages] = useState<ChatMessage[]>([]);
    const [hasMore, setHasMore] = useState(false);
    const [historyState, setHistoryState] = useState<HistoryState>("loading");
    const [historyAttempt, setHistoryAttempt] = useState(0);
    const [isLoadingOlder, setIsLoadingOlder] = useState(false);
    const [olderError, setOlderError] = useState(false);
    const [connection, setConnection] = useState<ConnectionState>("connecting");

    // Source of truth for decisions taken outside of render (socket handlers,
    // pagination guards); the state above only mirrors it for rendering.
    const messagesRef = useRef<ChatMessage[]>([]);
    const hasMoreRef = useRef(false);
    const loadingOlderRef = useRef(false);
    const socketRef = useRef<WebSocket | null>(null);
    const lastSentRef = useRef("");
    const pendingSeenRef = useRef(false);
    const seenTimerRef = useRef<number | undefined>(undefined);
    const deniedRef = useRef(false);

    const applyMessages = useCallback((update: (prev: ChatMessage[]) => ChatMessage[]) => {
        const next = update(messagesRef.current);
        messagesRef.current = next;
        setMessages(next);
    }, []);

    const applyHasMore = useCallback((value: boolean) => {
        hasMoreRef.current = value;
        setHasMore(value);
    }, []);

    /**
     * Returns true when the failure ends the conversation (no point retrying):
     * session expired (401: the profile refetch sends the user to /login) or
     * no longer a match / unknown user (403, 404).
     */
    const handleAccessFailure = useCallback((status: number): boolean => {
        if (status === 401) {
            void latest.current.refetchProfile();
            return true;
        }
        if (status === 403 || status === 404) {
            setConnection("denied");
            if (!deniedRef.current) {
                deniedRef.current = true;
                latest.current.onDenied();
            }
            return true;
        }
        return false;
    }, []);

    const markSeenNow = useCallback(async () => {
        if (document.visibilityState !== "visible") {
            pendingSeenRef.current = true; // sent when the tab becomes visible again
            return;
        }
        pendingSeenRef.current = false;
        try {
            const response = await markSeen(targetId);
            if (response.ok) latest.current.onSeen();
        } catch {
            // Best effort: the next incoming message or visit tries again.
        }
    }, [targetId]);

    /** Coalesces a burst of incoming messages into one request. */
    const requestSeen = useCallback(() => {
        window.clearTimeout(seenTimerRef.current);
        seenTimerRef.current = window.setTimeout(() => void markSeenNow(), SEEN_DEBOUNCE_MS);
    }, [markSeenNow]);

    // First page of history.
    useEffect(() => {
        let cancelled = false;
        setHistoryState("loading");

        void fetchPage(targetId).then((result) => {
            if (cancelled) return;
            if (!result.ok) {
                if (handleAccessFailure(result.status)) return;
                setHistoryState("error");
                latest.current.showError(result.message);
                return;
            }
            applyMessages((prev) => mergeMessages(prev, toAscending(result.page.messages)));
            applyHasMore(result.page.has_more);
            setHistoryState("ready");
            if (latest.current.initialUnread > 0) void markSeenNow();
        });

        return () => {
            cancelled = true;
        };
    }, [targetId, historyAttempt, applyMessages, applyHasMore, handleAccessFailure, markSeenNow]);

    // A hidden tab cannot have "seen" anything: catch up when it comes back.
    useEffect(() => {
        const onVisible = () => {
            if (document.visibilityState === "visible" && pendingSeenRef.current) void markSeenNow();
        };
        document.addEventListener("visibilitychange", onVisible);
        return () => document.removeEventListener("visibilitychange", onVisible);
    }, [markSeenNow]);

    useEffect(() => () => window.clearTimeout(seenTimerRef.current), []);

    // WebSocket, with reconnection.
    useEffect(() => {
        let disposed = false;
        let everOpened = false;
        let attempt = 0;
        let retryTimer: number | undefined;
        let socket: WebSocket | null = null;

        /** After a reconnection: fetch what was missed while offline. */
        async function resync() {
            const result = await fetchPage(targetId);
            if (disposed || !result.ok) return;

            const incoming = toAscending(result.page.messages);
            const known = messagesRef.current;
            const lastKnownId = known.length > 0 ? known[known.length - 1].id : 0;
            // More missed than one page holds: merging would leave a hole in
            // the middle, so start again from the newest page.
            const hasGap = result.page.has_more && incoming.length > 0 && incoming[0].id > lastKnownId;

            if (hasGap) {
                applyMessages(() => incoming);
                applyHasMore(true);
            } else {
                applyMessages((prev) => mergeMessages(prev, incoming));
            }
            if (incoming.some((m) => m.sender_id !== myId && m.id > lastKnownId)) requestSeen();
        }

        function handleFrame(raw: unknown) {
            if (typeof raw !== "string") return;
            let data: unknown;
            try {
                data = JSON.parse(raw);
            } catch {
                return;
            }

            if (isErrorFrame(data)) {
                latest.current.showError(data.detail);
                latest.current.onRejected(lastSentRef.current);
                return;
            }
            if (!isChatMessage(data)) return;

            applyMessages((prev) => mergeMessages(prev, [data]));
            latest.current.onMessage(data);
            if (data.sender_id !== myId) requestSeen();
        }

        /**
         * The browser reports any failed handshake as a bare close (1006), so a
         * refused connection (no longer a match, session expired) looks like a
         * network drop. A cheap authenticated request tells them apart.
         */
        async function recover() {
            setConnection(everOpened ? "reconnecting" : "connecting");
            const probe = await fetchPage(targetId, undefined, 1);
            if (disposed) return;
            if (!probe.ok && handleAccessFailure(probe.status)) return;

            const delay = Math.min(RETRY_BASE_MS * 2 ** attempt, RETRY_MAX_MS);
            attempt += 1;
            retryTimer = window.setTimeout(connect, delay);
        }

        function connect() {
            if (disposed) return;
            setConnection(everOpened ? "reconnecting" : "connecting");

            const current = new WebSocket(chatSocketUrl(targetId));
            socket = current;
            socketRef.current = current;

            current.onopen = () => {
                attempt = 0;
                setConnection("open");
                if (everOpened) void resync();
                everOpened = true;
            };
            current.onmessage = (event) => handleFrame(event.data);
            current.onclose = () => {
                if (socketRef.current === current) socketRef.current = null;
                if (!disposed) void recover();
            };
        }

        connect();

        return () => {
            disposed = true;
            window.clearTimeout(retryTimer);
            if (socket) {
                const leaving = socket;
                leaving.onmessage = null;
                leaving.onclose = null;
                // Closing a socket still connecting makes the browser print a warning in the
                // console ("closed before the connection is established"). In development React
                // mounts and unmounts the effect at once, so this happens on every chat page:
                // let it open, then close it.
                if (leaving.readyState === WebSocket.CONNECTING) leaving.onopen = () => leaving.close();
                else leaving.close();
            }
            socketRef.current = null;
        };
    }, [targetId, myId, applyMessages, applyHasMore, handleAccessFailure, requestSeen]);

    const loadOlder = useCallback(async () => {
        if (loadingOlderRef.current || !hasMoreRef.current) return;
        const oldest = messagesRef.current[0];
        if (!oldest) return;

        loadingOlderRef.current = true;
        setIsLoadingOlder(true);
        setOlderError(false);

        const result = await fetchPage(targetId, oldest.id);
        if (result.ok) {
            applyMessages((prev) => mergeMessages(prev, toAscending(result.page.messages)));
            applyHasMore(result.page.has_more);
        } else if (!handleAccessFailure(result.status)) {
            setOlderError(true);
            latest.current.showError(result.message);
        }

        loadingOlderRef.current = false;
        setIsLoadingOlder(false);
    }, [targetId, applyMessages, applyHasMore, handleAccessFailure]);

    const retryHistory = useCallback(() => setHistoryAttempt((n) => n + 1), []);

    /** Returns false (nothing sent) when the socket is not open. */
    const send = useCallback((content: string): boolean => {
        const socket = socketRef.current;
        if (!socket || socket.readyState !== WebSocket.OPEN) return false;
        lastSentRef.current = content;
        socket.send(JSON.stringify({ content }));
        return true;
    }, []);

    return {
        messages,
        historyState,
        hasMore,
        isLoadingOlder,
        olderError,
        connection,
        loadOlder,
        retryHistory,
        send,
    };
}
