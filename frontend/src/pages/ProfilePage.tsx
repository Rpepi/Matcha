import { Loader2, Eye } from "lucide-react";
import { Link } from "react-router-dom";
import { useProfileContext } from "@/context/ProfileContext";
import ProfilePhotos from "@/components/profile/ProfilePhotos";
import ProfileDetails from "@/components/profile/ProfileDetails";
import ProfileAbout from "@/components/userProfile/ProfileAbout";
import ProfileTags from "@/components/profile/ProfileTags";

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
        <div className="mx-auto flex max-w-6xl flex-col p-6 lg:min-h-dvh lg:justify-center lg:p-16">
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

            <div className="flex flex-col gap-10 lg:flex-row lg:items-start lg:gap-16">
                <div className="w-full shrink-0 lg:w-[360px]">
                    <ProfilePhotos photos={profile.photos} />
                </div>

                <div className="flex min-w-0 flex-1 flex-col gap-5">
                    <ProfileDetails profile={profile} />

                    <div className="h-px bg-grey/20" />

                    <ProfileAbout bio={profile.bio} />
                    <ProfileTags tags={profile.tags} />
                </div>
            </div>
        </div>
    );
}
