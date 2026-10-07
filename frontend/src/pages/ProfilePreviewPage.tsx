import { Loader2 } from "lucide-react";
import { useProfileContext } from "@/context/ProfileContext";
import ProfileDetailLayout from "@/components/userProfile/ProfileDetailLayout";

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
        <ProfileDetailLayout
            profile={profile}
            myTags={profile.tags}
            photoUrl={(photo) => `/api/profile/photos/${photo.position}?v=${encodeURIComponent(photo.path)}`}
            backTo="/profile"
            backLabel="Back to Profile"
        />
    );
}
