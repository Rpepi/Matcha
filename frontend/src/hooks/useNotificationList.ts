import { useCallback, useEffect, useRef, useState } from "react";
import { getNotification, markNotificationSeen, type AppNotification } from "@/api/notification";
import { useNotificationContext } from "@/context/NotificationContext";


const errorMessage = "Error while fetching notifications"

export default function useNotificationList() {
    const [notificationList, setNotificationList] = useState<AppNotification[]>([]);
    // Ids that were unread when they reached this screen. The server has them as read as soon as
    // they are shown, but they stay highlighted for the whole visit so the user sees what is new.
    const [highlightedIds, setHighlightedIds] = useState<ReadonlySet<number>>(new Set());
    const [isLoading, setIsLoading] = useState(true);
    const [error, setError] = useState<string | null>(null);
    const { refreshUnreadCount, eventVersion } = useNotificationContext();

    const latestRequest = useRef(0);
    const hasLoaded = useRef(false);

    // `silent`: a refresh because something just arrived. No spinner, and no error screen
    // over a list that is already there. A request that replaces an earlier one inherits
    // its job: when it ends, loading ends (and only the newest answer is kept).
    const load = useCallback(async (silent = false) => {
        const requestId = ++latestRequest.current;
        if (!silent) {
            setIsLoading(true);
            setError(null);
        }
        try {
            const response = await getNotification();
            if (requestId !== latestRequest.current) return;
            if (response.ok)
            {
                const data = await response.json() as AppNotification[];
                if (requestId !== latestRequest.current) return;
                if (Array.isArray(data))
                {
                    hasLoaded.current = true;
                    setNotificationList(data);
                    setError(null);
                    if (data.some((n) => !n.seen))
                    {
                        setHighlightedIds((previous) => {
                            const next = new Set(previous);
                            data.forEach((n) => { if (!n.seen) next.add(n.id); });
                            return next;
                        });
                        try {
                            const seenResponse = await markNotificationSeen();
                            if (seenResponse.ok)
                                await refreshUnreadCount()
                        }
                        catch {}
                    }
                }
                else
                    setError(errorMessage)
            }
            else {
                if (!silent || !hasLoaded.current) setError(errorMessage)
            }
        } catch {
            if (requestId === latestRequest.current && (!silent || !hasLoaded.current)) setError(errorMessage)
        }
        finally {
            if (requestId === latestRequest.current) setIsLoading(false);
        }
    }, [refreshUnreadCount]);

    useEffect(() => {
        void load()
    }, [load]);

    // Something arrived while the page is open: reload the list quietly.
    const handledVersion = useRef(eventVersion);
    useEffect(() => {
        if (eventVersion === handledVersion.current) return;
        handledVersion.current = eventVersion;
        void load(true);
    }, [eventVersion, load]);

    const retry = useCallback(() => load(false), [load]);

    return { notifications: notificationList, highlightedIds, isLoading, error, retry };
}
