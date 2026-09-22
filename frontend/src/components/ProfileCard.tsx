import { Link } from "react-router-dom";
import { UserRound } from "lucide-react";
import type { BrowseProfile } from "../api/browse";

export default function ProfileCard({ profile }: { profile: BrowseProfile }) {
    return (
        <Link
            to={`/users/${profile.id}`}
            className="group flex h-80 w-64 flex-none flex-col overflow-hidden rounded-2xl border-3 border-grey/15 bg-paper transition hover:border-matcha"
        >
            <div className="relative flex flex-1 items-center justify-center bg-grey/10">
                <UserRound className="h-20 w-20 text-grey/40" />
                {profile.is_online && (
                    <span className="absolute right-3 top-3 h-3 w-3 rounded-full bg-matcha ring-2 ring-paper" />
                )}
            </div>
            <div className="flex-none p-3">
                <p className="truncate font-medium text-ink">
                    {profile.first_name}{profile.age !== null ? `, ${profile.age}` : ""}
                </p>
                <p className="truncate text-sm text-grey">
                    {profile.city ?? "Unknown location"}
                    {profile.distance_km !== null ? ` · ${profile.distance_km} km` : ""}
                </p>
            </div>
        </Link>
    );
}
