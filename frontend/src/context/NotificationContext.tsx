import { createContext, useContext, type ReactNode, useRef, useCallback, useEffect, useMemo, useState } from "react";
import { useUnreadCount } from "@/hooks/useUnreadCount";
import { useProfileContext } from "@/context/ProfileContext";
import { useNotificationStream } from "@/hooks/useNotificationStream";

const REFRESH_DEBOUNCE_MS = 400;
const NOTIFICATION_RELEVANT = new Set(["message", "match", "unlike", "like", "visit"]);

interface NotificationContextValue {
    unreadCount: number;
    refreshUnreadCount: () => Promise<void>;
    /** Goes up each time something arrives (or the stream comes back): the notification page reloads its list on it. */
    eventVersion: number;
}

export const NotificationContext = createContext<NotificationContextValue | undefined>(undefined);

export function NotificationProvider ({ children }: { children: ReactNode}) {
    const { status } = useProfileContext();
    const  enabled = status === "complete";
    const {unreadCount, refreshUnreadCount} = useUnreadCount(enabled);

    const [eventVersion, setEventVersion] = useState(0);
    const refreshTimer = useRef<number | undefined>(undefined);
    const scheduleRefresh = useCallback(() => {
        window.clearTimeout(refreshTimer.current);
        refreshTimer.current = window.setTimeout(() => {
            void refreshUnreadCount();
            setEventVersion((v) => v + 1);
        }, REFRESH_DEBOUNCE_MS);
    }, [refreshUnreadCount]);
    useEffect(() => () => window.clearTimeout(refreshTimer.current), []);

    useEffect(() => {
        if (!enabled) return;
        const onVisible = () => {
            if (document.visibilityState === "visible") scheduleRefresh();
        };
        document.addEventListener("visibilitychange", onVisible);
        return () => document.removeEventListener("visibilitychange", onVisible);
    }, [enabled, scheduleRefresh]);

    useNotificationStream(enabled, NOTIFICATION_RELEVANT, scheduleRefresh, scheduleRefresh);

    const value = useMemo(
        () => ({ unreadCount, refreshUnreadCount, eventVersion }),
        [unreadCount, refreshUnreadCount, eventVersion],
    );

    return <NotificationContext.Provider value={value}>{children}</NotificationContext.Provider>;
}

export function useNotificationContext(): NotificationContextValue {
    const ctx = useContext(NotificationContext);                             
    if (!ctx) throw new Error("useNotificationContext must be used within a NotificationProvider");
    return ctx;                                                
}
