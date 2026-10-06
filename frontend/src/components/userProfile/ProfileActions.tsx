import { Link, useNavigate } from "react-router-dom";
import { Heart, MessageCircle } from "lucide-react";
import type { UserProfileDetail } from "@/api/users";
import BlockButton from "@/components/BlockButton";
import LikeButton from "@/components/LikeButton";
import { useBrowseContext } from "@/context/BrowseContext";
import { useBlock } from "@/hooks/useBlock";
import { useLike } from "@/hooks/useLike";

export default function ProfileActions({ profile }: { profile: UserProfileDetail }) {
    const navigate = useNavigate();
    const { removeProfile } = useBrowseContext();
    const { block, isBlocking } = useBlock(profile.id, profile.first_name, () => {
        removeProfile(profile.id); // its card must not stay in the loaded pages
        navigate("/browse", { replace: true });
    });
    const { liked, isMatch, isPending, canLike, toggle } = useLike(
        profile.id,
        profile.first_name,
        { liked: profile.is_liked_by_me, match: profile.is_match },
    );

    return (
        <div className="flex flex-col gap-4">
            {(isMatch || profile.likes_me) && (
                <p className="flex w-fit items-center gap-2 rounded-full bg-pink/15 px-4 py-1.5 text-sm font-medium text-ink">
                    <Heart className="h-4 w-4 fill-pink text-pink" aria-hidden="true" />
                    {isMatch ? `You and ${profile.first_name} are connected` : `${profile.first_name} likes you`}
                </p>
            )}

            <div className="flex flex-wrap items-center gap-3">
                <LikeButton
                    variant="pill"
                    liked={liked}
                    isPending={isPending}
                    canLike={canLike}
                    onToggle={toggle}
                    name={profile.first_name}
                />

                {isMatch && (
                    <Link
                        to={`/chat/${profile.id}`}
                        className="flex items-center gap-2 rounded-full bg-grey/10 px-6 py-3 font-medium text-ink transition hover:bg-matcha/25 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-matcha"
                    >
                        <MessageCircle className="h-5 w-5" aria-hidden="true" />
                        Message
                    </Link>
                )}

                <BlockButton name={profile.first_name} onConfirm={block} isBlocking={isBlocking} />
            </div>
        </div>
    );
}
