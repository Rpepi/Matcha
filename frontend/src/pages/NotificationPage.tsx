import NotificationList from "@/components/notifications/notificationList";
import useNotificationList from "@/hooks/useNotificationList";

export default function NotificationPage() {
    const { notifications, highlightedIds, isLoading, error, retry } = useNotificationList();

    return (
        <div className="mx-auto flex min-h-dvh max-w-2xl flex-col p-6 md:p-10">
            <header className="mb-6">
                <h1 className="font-display text-3xl font-medium text-ink">Notifications</h1>
                <p className="mt-1 text-sm text-grey">Likes, visits, matches and messages.</p>
            </header>

            <NotificationList
                notifications={notifications}
                highlightedIds={highlightedIds}
                isLoading={isLoading}
                error={error}
                retry={retry}
            />
        </div>
    );
}
