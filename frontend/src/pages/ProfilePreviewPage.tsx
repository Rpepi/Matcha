import { Loader2 } from "lucide-react";
import { useProfileContext } from "@/context/ProfileContext";
import ProfilePhotoGallery from "@/components/userProfile/ProfilePhotoGallery";
import ProfileHeader from "@/components/userProfile/ProfileHeader";
import ProfileMeta from "@/components/userProfile/ProfileMeta";
import ProfileAbout from "@/components/userProfile/ProfileAbout";
import ProfileInterests from "@/components/userProfile/ProfileInterests";
import OnlineStatus from "@/components/userProfile/OnlineStatus";

export default function ProfilePreviewPage() {
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
            <div className="flex flex-col gap-10 lg:flex-row lg:items-start lg:gap-16">
                <ProfilePhotoGallery
                    profile={profile}
                    photoUrl={(photo) => `/api/profile/photos/${photo.position}?v=${encodeURIComponent(photo.path)}`}
                    backTo="/profile"
                    backLabel="Back to Profile"
                />

                <div className="flex min-w-0 flex-1 flex-col gap-5">
                    <div className="flex flex-col gap-5">
                        <OnlineStatus profile={profile} />
                        <ProfileHeader profile={profile} />
                        <ProfileMeta profile={profile} />
                    </div>

                    <div className="h-px bg-grey/20" />

                    <ProfileAbout bio={profile.bio} />
                    <ProfileInterests tags={profile.tags} myTags={profile.tags} />
                </div>
            </div>
        </div>
    );
}
