import { Loader2, BellIcon, Heart, HeartCrack, HeartHandshake, Eye, MessageCircle } from "lucide-react";
import type { ReactNode } from "react";
import type { LucideIcon } from "lucide-react";
import { Link } from "react-router-dom";
import type { AppNotification } from "@/api/notification";
import { formatListTime } from "@/lib/chatTime";

interface NotificationListProps {
    notifications: AppNotification[];
    /** Notifications to show as new, even if the server already has them as read (see useNotificationList). */
    highlightedIds: ReadonlySet<number>;
    isLoading: boolean;
    error: string | null;
    retry: () => void;
}

interface NotificationDisplay {
    Icon: LucideIcon;
    /** Colors of the round icon: a different tint per kind so the list can be scanned at a glance. */
    tone: string;
    text: ReactNode;
    to: string;
}

function describe(notification: AppNotification): NotificationDisplay {
    const name = <span className="font-semibold">{notification.first_name}</span>;
    const profile = `/users/${notification.from_user_id}`;
    const chat = `/chat/${notification.from_user_id}`;

    switch (notification.type) {
        case "like":
            return { Icon: Heart, tone: "bg-pink/20 text-pink", to: profile, text: <>{name} liked you</> };
        case "match":
            return { Icon: HeartHandshake, tone: "bg-matcha/30 text-matcha-dark", to: chat, text: <>You and {name} are now connected</> };
        case "visit":
            return { Icon: Eye, tone: "bg-grey/15 text-ink/70", to: profile, text: <>{name} viewed your profile</> };
        case "message":
            return { Icon: MessageCircle, tone: "bg-orchid/15 text-orchid", to: chat, text: <>{name} sent you a message</> };
        case "unlike":
            return { Icon: HeartCrack, tone: "bg-grey/15 text-grey", to: profile, text: <>{name} unliked you</> };
    }
}

function NotificationItem({ notification, highlighted }: { notification: AppNotification; highlighted: boolean }) {
    const { Icon, tone, text, to } = describe(notification);
    const unread = !notification.seen || highlighted;

    return (
        <Link
            to={to}
            className={`flex items-center gap-4 rounded-2xl px-4 py-3.5 transition hover:bg-matcha/25 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-[-2px] focus-visible:outline-matcha ${
                unread ? "bg-matcha/15" : ""
            }`}
        >
            <span className={`flex h-11 w-11 shrink-0 items-center justify-center rounded-full ${tone}`}>
                <Icon className="h-5 w-5" aria-hidden="true" />
            </span>

            <span className="min-w-0 flex-1">
                <span className={`block text-[15px] text-ink ${unread ? "font-medium" : ""}`}>{text}</span>
                <span className="block text-xs text-grey">{formatListTime(notification.created_at)}</span>
            </span>

            {unread && (
                <>
                    <span aria-hidden="true" className="h-2.5 w-2.5 shrink-0 rounded-full bg-pink" />
                    <span className="sr-only">Unread</span>
                </>
            )}
        </Link>
    );
}

export default function NotificationList({ notifications, highlightedIds, isLoading, error, retry }: NotificationListProps) {
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
                    onClick={retry}
                    className="cursor-pointer rounded-full bg-grey/10 px-5 py-2 text-sm font-medium text-ink transition hover:bg-matcha/25"
                >
                    Try again
                </button>
            </div>
        );
    }

    if (notifications.length === 0) {
        return (
            <div className="flex flex-1 flex-col items-center justify-center gap-3 p-8 text-center">
                <span className="flex h-14 w-14 items-center justify-center rounded-full bg-matcha/25">
                    <BellIcon className="h-7 w-7 text-ink" />
                </span>
                <p className="font-display text-lg text-ink">Nothing Happened ...</p>
                <p className="text-sm text-grey">You will receive notifications for new messages, match or likes.</p>
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
        <nav aria-label="Notifications">
            <ul className="flex flex-col gap-2">
                {notifications.map((notification) => (
                    <li key={notification.id}>
                        <NotificationItem notification={notification} highlighted={highlightedIds.has(notification.id)} />
                    </li>
                ))}
            </ul>
        </nav>
    );
}
