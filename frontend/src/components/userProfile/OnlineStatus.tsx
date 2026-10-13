import { formatLastSeenAt } from "@/lib/chatTime";

interface OnlineStatusProps {
    profile: {
        is_online: boolean;
        last_seen: string | null;
    };
}

export default function OnlineStatus({ profile }: OnlineStatusProps) {
    return (
        <div className="flex items-center gap-2 text-sm font-medium text-ink/80">
            <span className={`h-2 w-2 rounded-full ${profile.is_online ? "bg-matcha" : "bg-grey/50"}`} />
            {profile.is_online ? "Active now" : formatLastSeenAt(profile.last_seen)}
        </div>
    );
}
