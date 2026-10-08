import type { ReactNode } from "react";
import { Link } from "react-router-dom";
import { Loader2 } from "lucide-react";
import { formatListTime } from "@/lib/chatTime";
import Avatar from "./Avatar";

interface ProfileEntry {
    id: number;
    first_name: string;
    created_at: string;
    photo_position: number | null;
}

interface PeopleListProps<T extends ProfileEntry> {
    entries: T[];
    isLoading: boolean;
    loadError: boolean;
    retry: () => void;
    getPersonId: (entry: T) => number;
    icon: ReactNode;
    ariaLabel: string;
    emptyTitle: string;
    emptyDescription: string;
    actionText: string;
    loadErrorText: string;
}

export default function PeopleList<T extends ProfileEntry>({
    entries,
    isLoading,
    loadError,
    retry,
    getPersonId,
    icon,
    ariaLabel,
    emptyTitle,
    emptyDescription,
    actionText,
    loadErrorText,
}: PeopleListProps<T>) {
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
                <p className="text-sm text-grey">{loadErrorText}</p>
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

    if (entries.length === 0) {
        return (
            <div className="flex flex-1 flex-col items-center justify-center gap-3 p-8 text-center">
                <span className="flex h-14 w-14 items-center justify-center rounded-full bg-matcha/25">{icon}</span>
                <p className="font-display text-lg text-ink">{emptyTitle}</p>
                <p className="text-sm text-grey">{emptyDescription}</p>
            </div>
        );
    }

    return (
        <nav aria-label={ariaLabel} className="min-h-0 flex-1 overflow-y-auto px-2 pb-2">
            <ul className="flex flex-col gap-0.5">
                {entries.map((entry) => {
                    const personId = getPersonId(entry);
                    return (
                        <li key={entry.id}>
                            <Link
                                to={`/users/${personId}`}
                                className="flex items-center gap-3 rounded-2xl px-3 py-3 transition hover:bg-matcha/25 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-[-2px] focus-visible:outline-matcha"
                            >
                                <Avatar
                                    user={{
                                        id: personId,
                                        first_name: entry.first_name,
                                        is_online: false,
                                        last_seen: null,
                                        photo: entry.photo_position !== null ? `/users/${personId}/photos/${entry.photo_position}` : null,
                                    }}
                                    size={52}
                                />
                                <div className="min-w-0 flex-1">
                                    <div className="flex items-baseline justify-between gap-2">
                                        <span className="truncate text-[15px] font-medium text-ink">{entry.first_name}</span>
                                        <span className="shrink-0 text-xs text-grey">{formatListTime(entry.created_at)}</span>
                                    </div>
                                    <span className="text-sm text-grey">{actionText}</span>
                                </div>
                            </Link>
                        </li>
                    );
                })}
            </ul>
        </nav>
    );
}
