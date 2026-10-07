import { useParams } from "react-router-dom";
import { Loader2 } from "lucide-react";
import { useUserProfile } from "@/hooks/useUserProfile";
import { useProfileContext } from "@/context/ProfileContext";
import ProfileDetailLayout from "@/components/userProfile/ProfileDetailLayout";
import ProfileActions from "@/components/userProfile/ProfileActions";
import ReportMenu from "@/components/userProfile/ReportMenu";

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
        <ProfileDetailLayout
            profile={profile}
            myTags={myProfile?.tags ?? []}
            photoUrl={(photo) => `/api/users/${profile.id}/photos/${photo.position}?v=${encodeURIComponent(photo.path)}`}
            backTo="/browse"
            backLabel="Back to Browse"
            topRight={<ReportMenu userId={profile.id} firstName={profile.first_name} />}
            actions={<ProfileActions profile={profile} />}
        />
    );
}
