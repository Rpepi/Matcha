import { Link } from "react-router-dom";
import type { BrowseProfile } from "../api/browse";
import { CARD_ASPECT_RATIO } from "../lib/browseLayout";

function placeholderPhotoUrl(profile: BrowseProfile): string {
    const folder = profile.gender === "male" ? "men" : "women";
    const index = profile.id % 100;
    return `https://randomuser.me/api/portraits/${folder}/${index}.jpg`;
}

export default function ProfileCard({ profile }: { profile: BrowseProfile }) {
    return (
        <Link
            to={`/users/${profile.id}`}
            className="group flex h-full w-full flex-col"
        >
            <div
                className="relative w-full overflow-hidden rounded-[55px] bg-grey/10"
                style={{ aspectRatio: CARD_ASPECT_RATIO }}
            >
                <img
                    src={placeholderPhotoUrl(profile)}
                    alt=""
                    className="h-full w-full object-cover"
                />
                {profile.is_online && (
                    <span className="absolute right-3 top-3 h-3 w-3 rounded-full bg-matcha ring-2 ring-paper" />
                )}
            </div>
            <div className="p-3">
                <p className="truncate font-medium text-ink">
                    {profile.first_name}{profile.age !== null ? `, ${profile.age}` : ""}
                </p>
            </div>
        </Link>
    );
}
