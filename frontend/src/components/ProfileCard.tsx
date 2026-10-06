import { useState } from "react";
import { Link } from "react-router-dom";
import type { BrowseProfile } from "../api/browse";
import { CARD_ASPECT_RATIO } from "../lib/browseLayout";
import { useLike } from "../hooks/useLike";
import LikeButton from "./LikeButton";
import PhotoFallback from "./PhotoFallback";

export default function ProfileCard({ profile }: { profile: BrowseProfile }) {
    const { liked, isPending, canLike, toggle } = useLike(
        profile.id,
        profile.first_name,
        { liked: profile.is_liked_by_me, match: false },
    );

    const [failedSrc, setFailedSrc] = useState<string | null>(null);
    const src = profile.photo_position !== null ? `/api/users/${profile.id}/photos/${profile.photo_position}` : null;

    // The heart is a sibling of the link, not a child: a button inside an
    // anchor is invalid HTML and its click would also open the profile.
    return (
        <div className="relative h-full w-full transition-transform duration-300 hover:scale-[1.02]">
            <Link
                to={`/users/${profile.id}`}
                className="group flex h-full w-full flex-col"
            >
                <div
                    className="relative w-full overflow-hidden rounded-[35px] bg-grey/10 cursor-pointer"
                    style={{ aspectRatio: CARD_ASPECT_RATIO }}
                >
                    {src !== null && failedSrc !== src ? (
                        <img
                            src={src}
                            alt=""
                            onError={() => setFailedSrc(src)}
                            className="h-full w-full object-cover"
                        />
                    ) : (
                        <PhotoFallback name={profile.first_name} />
                    )}
                    <div className="pointer-events-none absolute inset-x-0 bottom-0 h-2/5 backdrop-blur-md [mask-image:linear-gradient(to_top,black,transparent)] [-webkit-mask-image:linear-gradient(to_top,black,transparent)]" />
                    <div className="pointer-events-none absolute inset-x-0 bottom-0 h-2/5 bg-gradient-to-t from-ink/85 to-transparent" />
                    {profile.is_online && (
                        <span className="absolute right-3 top-3 h-3 w-3 rounded-full bg-matcha ring-2 ring-paper" />
                    )}
                    <div className="absolute inset-x-0 bottom-0 flex flex-col px-6 pr-16 pb-4">
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

            <LikeButton
                liked={liked}
                isPending={isPending}
                canLike={canLike}
                onToggle={toggle}
                name={profile.first_name}
                className="absolute right-4 bottom-4"
            />
        </div>
    );
}
