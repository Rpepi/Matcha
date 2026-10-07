import { Link } from "react-router-dom";
import { Loader2, Eye } from "lucide-react";
import { useProfileVisits } from "@/hooks/useProfileVisits";
import { formatListTime } from "@/lib/chatTime";
import Avatar from "./Avatar";

export default function VisitorsList() {
    const { visits, isLoading, loadError, retry } = useProfileVisits();

    if (isLoading) {
        return (
            <div className="flex flex-1 items-center justify-center">
                <Loader2 className="h-6 w-6 animate-spin text-matcha" />
            </div>
        );
    }

    if (loadError) {
        return (
            <div className="flex flex-1 flex-col items-center justify-center gap-3 p-6 text-center">
                <p className="text-sm text-grey">Could not load visitors. Please try again.</p>
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

    if (visits.length === 0) {
        return (
            <div className="flex flex-1 flex-col items-center justify-center gap-3 p-8 text-center">
                <span className="flex h-14 w-14 items-center justify-center rounded-full bg-matcha/25">
                    <Eye className="h-7 w-7 text-ink" />
                </span>
                <p className="font-display text-lg text-ink">No visitors yet</p>
                <p className="text-sm text-grey">People who view your profile will show up here.</p>
            </div>
        );
    }

    return (
        <nav aria-label="Visitors" className="min-h-0 flex-1 overflow-y-auto px-2 pb-2">
            <ul className="flex flex-col gap-0.5">
                {visits.map((visit) => (
                    <li key={visit.id}>
                        <Link
                            to={`/users/${visit.visitor_id}`}
                            className="flex items-center gap-3 rounded-2xl px-3 py-3 transition hover:bg-matcha/25 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-[-2px] focus-visible:outline-matcha"
                        >
                            <Avatar
                                user={{
                                    id: visit.visitor_id,
                                    first_name: visit.first_name,
                                    is_online: false,
                                    last_seen: null,
                                    photo: visit.photo_position !== null ? `/users/${visit.visitor_id}/photos/${visit.photo_position}` : null,
                                }}
                                size={52}
                            />
                            <div className="min-w-0 flex-1">
                                <div className="flex items-baseline justify-between gap-2">
                                    <span className="truncate text-[15px] font-medium text-ink">{visit.first_name}</span>
                                    <span className="shrink-0 text-xs text-grey">{formatListTime(visit.created_at)}</span>
                                </div>
                                <span className="text-sm text-grey">Viewed your profile</span>
                            </div>
                        </Link>
                    </li>
                ))}
            </ul>
        </nav>
    );
}
