import { ChevronDown, Loader2 } from "lucide-react";
import { useProfileBlockedUsers } from "@/hooks/useProfileBlockedUsers";

export default function ProfileBlockedUsers() {
    const { blockedUsers, isLoading, loadError, isExpanded, toggleExpanded, unblockingId, unblock } = useProfileBlockedUsers();

    return (
        <div className="flex flex-col gap-3">
            <h2 className="text-xs font-semibold tracking-widest text-grey uppercase">Blocked users</h2>

            {isLoading ? (
                <Loader2 className="h-5 w-5 animate-spin text-matcha" />
            ) : loadError ? (
                <p className="text-sm text-pink">Could not load blocked users. Please try again.</p>
            ) : blockedUsers.length === 0 ? (
                <p className="text-sm text-grey/50 italic">None</p>
            ) : (
                <div className="flex flex-col gap-2">
                    <button
                        type="button"
                        onClick={toggleExpanded}
                        className="flex w-fit cursor-pointer items-center gap-1.5 text-sm font-medium text-ink/80 transition hover:text-ink"
                    >
                        {blockedUsers.length} blocked
                        <ChevronDown className={`h-4 w-4 transition-transform ${isExpanded ? "rotate-180" : ""}`} />
                    </button>

                    {isExpanded && (
                        <ul className="flex flex-col divide-y divide-grey/10">
                            {blockedUsers.map((user) => (
                                <li key={user.id} className="flex items-center justify-between py-2">
                                    <span className="text-ink">{user.first_name}</span>
                                    <button
                                        type="button"
                                        onClick={() => unblock(user.id)}
                                        disabled={unblockingId === user.id}
                                        className="cursor-pointer rounded-full px-2.5 py-1 text-sm font-medium text-grey transition hover:bg-grey/10 hover:text-ink disabled:cursor-not-allowed disabled:opacity-60"
                                    >
                                        Unblock
                                    </button>
                                </li>
                            ))}
                        </ul>
                    )}
                </div>
            )}
        </div>
    );
}
