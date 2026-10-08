import { Loader2, Eye, LogOut } from "lucide-react";
import { Link } from "react-router-dom";
import { useProfileContext } from "@/context/ProfileContext";
import { useToast } from "@/context/ToastContext";
import { logout } from "@/api/auth";
import ProfilePhotos from "@/components/profile/ProfilePhotos";
import ProfileDetails from "@/components/profile/ProfileDetails";
import ProfileBio from "@/components/profile/ProfileBio";
import ProfileTags from "@/components/profile/ProfileTags";
import ProfileEmail from "@/components/profile/ProfileEmail";
import ProfileCity from "@/components/profile/ProfileCity";
import ProfileBlockedUsers from "@/components/profile/ProfileBlockedUsers";
import ProfileSection from "@/components/profile/ProfileSection";

export default function ProfilePage() {
    const { status, profile, refetch } = useProfileContext();
    const { showError } = useToast();

    async function handleLogout() {
        try {
            const response = await logout();
            if (!response.ok) {
                showError("Could not log out. Please try again.");
                return;
            }
            await refetch();
        } catch {
            showError("Could not log out. Please check your connection and try again.");
        }
    }

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
                <ProfileSection className="flex flex-col gap-6">
                    <ProfilePhotos photos={profile.photos} />
                    <ProfileTags tags={profile.tags} />
                    <ProfileBio bio={profile.bio} />
                </ProfileSection>

                <ProfileSection>
                    <ProfileDetails profile={profile} />
                </ProfileSection>

                <ProfileSection>
                    <ProfileEmail email={profile.email} />
                </ProfileSection>

                <ProfileSection>
                    <ProfileCity city={profile.city} />
                </ProfileSection>

                <ProfileSection>
                    <ProfileBlockedUsers />
                </ProfileSection>

                <button
                    type="button"
                    onClick={handleLogout}
                    className="flex items-center justify-center gap-2 rounded-3xl px-4 py-3 font-medium text-pink transition bg-pink/15 md:hidden"
                >
                    <LogOut className="h-5 w-5" />
                    Log out
                </button>
            </div>
        </div>
    );
}
