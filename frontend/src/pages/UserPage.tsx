import { useParams } from "react-router-dom";
import { Loader2 } from "lucide-react";
import { useUserProfile } from "@/hooks/useUserProfile";
import { useProfileContext } from "@/context/ProfileContext";
import ProfilePhotoGallery from "@/components/userProfile/ProfilePhotoGallery";
import ProfileHeader from "@/components/userProfile/ProfileHeader";
import ProfileMeta from "@/components/userProfile/ProfileMeta";
import ProfileActions from "@/components/userProfile/ProfileActions";
import ProfileAbout from "@/components/userProfile/ProfileAbout";
import ProfileInterests from "@/components/userProfile/ProfileInterests";

export default function UserPage() {
    const { id } = useParams<{ id: string }>();
    const userId = Number(id);
    const { profile, isLoading, error } = useUserProfile(userId);
    const { profile: myProfile } = useProfileContext();

    if (isLoading) {
        return (
            <div className="flex min-h-dvh items-center justify-center">
                <Loader2 className="h-6 w-6 animate-spin text-matcha" />
            </div>
        );
    }

    if (error || !profile) {
        return (
            <div className="flex min-h-dvh items-center justify-center p-6">
                <p className="text-sm text-grey">{error ?? "This profile could not be found."}</p>
            </div>
        );
    }

    return (
        <div className="mx-auto max-w-6xl p-6 lg:flex lg:min-h-dvh lg:items-center lg:p-16">
            <div className="flex flex-col gap-5 lg:w-full lg:flex-row lg:items-start lg:gap-16">
                <ProfilePhotoGallery
                    profile={profile}
                    photoUrl={(photo) => `/api/users/${profile.id}/photos/${photo.position}?v=${encodeURIComponent(photo.path)}`}
                    backTo="/browse"
                    backLabel="Back to Browse"
                />

                <div className="flex min-w-0 flex-1 flex-col gap-10">
                    <div className="flex flex-col gap-5">
                        <ProfileHeader profile={profile} />
                        <ProfileMeta profile={profile} />
                        <ProfileActions profile={profile} />
                    </div>

                    <div className="h-px bg-grey/20" />

                    <ProfileAbout bio={profile.bio} />
                    <ProfileInterests tags={profile.tags} myTags={myProfile?.tags ?? []} />
                </div>
            </div>
        </div>
    );
}
