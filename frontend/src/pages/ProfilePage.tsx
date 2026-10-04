import { Loader2, Eye } from "lucide-react";
import { Link } from "react-router-dom";
import { useProfileContext } from "@/context/ProfileContext";
import ProfilePhotos from "@/components/profile/ProfilePhotos";
import ProfileDetails from "@/components/profile/ProfileDetails";
import ProfileBio from "@/components/profile/ProfileBio";
import ProfileTags from "@/components/profile/ProfileTags";
import ProfileCity from "@/components/profile/ProfileCity";

export default function ProfilePage() {
    const { status, profile } = useProfileContext();

    if (status === "loading" || !profile) {
        return (
            <div className="flex min-h-dvh items-center justify-center">
                <Loader2 className="h-6 w-6 animate-spin text-matcha" />
            </div>
        );
    }

    return (
        <div className="mx-auto flex max-w-2xl flex-col p-6 lg:p-16">
            <div className="mb-8 flex items-center justify-between">
                <h1 className="font-display text-3xl font-medium text-ink">My Profile</h1>
                <Link
                    to="/profile/preview"
                    className="flex items-center gap-2 rounded-full border border-grey/30 px-4 py-2 text-sm font-medium text-ink transition hover:bg-grey/10"
                >
                    <Eye className="h-4 w-4" />
                    Preview
                </Link>
            </div>

            <div className="flex flex-col gap-6">
                <div className="flex flex-col gap-6 rounded-3xl bg-grey/5 p-6">
                    <ProfilePhotos photos={profile.photos} />
                    <ProfileTags tags={profile.tags} />
                    <ProfileBio bio={profile.bio} />
                </div>

                <div className="flex flex-col gap-5 rounded-3xl bg-grey/5 p-6">
                    <ProfileDetails profile={profile} />
                </div>

                <div className="flex flex-col gap-3 rounded-3xl bg-grey/5 p-6">
                    <ProfileCity city={profile.city} />
                </div>
            </div>
        </div>
    );
}
