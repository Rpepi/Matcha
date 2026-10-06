import { useCallback, useEffect, useState } from "react";
import { getUnreadCount, UnreadNotificationCount} from "@/api/notification";

export function useUnreadCount(enabled: boolean) {
    const [unreadCount, setUnreadCount] = useState(0);

    const load = useCallback(async () =>  {
            try {
                const response = await getUnreadCount()
                if (response.ok)
                {
                    const data = await response.json() as UnreadNotificationCount
                    setUnreadCount(data.unread)
                }
            } catch {} // a non updated badge is better thant an error: following event will reload it
        }, [])

    useEffect(() => {
        if (!enabled) {
            setUnreadCount(0);
            return;
        }
        void load()
    }, [enabled, load]);

    return { unreadCount, refreshUnreadCount: load}
}