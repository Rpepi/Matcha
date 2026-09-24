import { Link } from "react-router-dom";
import type { BrowseProfile } from "../api/browse";
import { CARD_ASPECT_RATIO } from "../lib/browseLayout";

function placeholderPhotoUrl(profile: BrowseProfile): string {
    const index = (profile.id % 70) + 1;
    return `https://i.pravatar.cc/600?img=${index}`;
}

export default function ProfileCard({ profile }: { profile: BrowseProfile }) {
    return (
        <Link
            to={`/users/${profile.id}`}
            className="group flex h-full w-full flex-col"
        >
            <div
                className="relative w-full overflow-hidden rounded-[35px] bg-grey/10 cursor-pointer  transition-transform duration-300 group-hover:scale-[1.02]"
                style={{ aspectRatio: CARD_ASPECT_RATIO }}
            >
                <img
                    src={placeholderPhotoUrl(profile)}
                    alt=""
                    className="h-full w-full object-cover"
                />
                <div className="pointer-events-none absolute inset-x-0 bottom-0 h-2/5 backdrop-blur-md [mask-image:linear-gradient(to_top,black,transparent)] [-webkit-mask-image:linear-gradient(to_top,black,transparent)]" />
                <div className="pointer-events-none absolute inset-x-0 bottom-0 h-2/5 bg-gradient-to-t from-ink/85 to-transparent" />
                {profile.is_online && (
                    <span className="absolute right-3 top-3 h-3 w-3 rounded-full bg-matcha ring-2 ring-paper" />
                )}
                <div className="absolute inset-x-0 bottom-0 flex flex-col px-6 pb-4">
                    <div className="flex flex-row items-center gap-2">
                        <p className="text-2xl truncate font-bold text-paper">
                            {profile.first_name},
                        </p>
                        <p className="text-2xl text-paper/80">
                            {profile.age}
                        </p>
                    </div>
                    <p className="text-sm text-paper/80">
                        {profile.distance_km}km
                    </p>
                </div>
            </div>
        </Link>
    );
}
