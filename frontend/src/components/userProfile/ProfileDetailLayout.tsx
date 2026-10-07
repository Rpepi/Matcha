import type { ReactNode } from "react";
import type { UserPhoto } from "@/api/users";
import ProfilePhotoGallery from "@/components/userProfile/ProfilePhotoGallery";
import ProfileHeader from "@/components/userProfile/ProfileHeader";
import ProfileMeta from "@/components/userProfile/ProfileMeta";
import ProfileAbout from "@/components/userProfile/ProfileAbout";
import ProfileInterests from "@/components/userProfile/ProfileInterests";
import OnlineStatus from "@/components/userProfile/OnlineStatus";

interface ProfileDetailLayoutProps {
    profile: {
        id: number;
        first_name: string;
        birth_date: string | null;
        fame_rating: number;
        gender: string | null;
        city: string | null;
        bio: string | null;
        tags: string[];
        is_online: boolean;
        photos: UserPhoto[];
    };
    myTags: string[];
    photoUrl: (photo: UserPhoto) => string;
    backTo: string;
    backLabel: string;
    topRight?: ReactNode;
    actions?: ReactNode;
}

export default function ProfileDetailLayout({ profile, myTags, photoUrl, backTo, backLabel, topRight, actions }: ProfileDetailLayoutProps) {
    return (
        <div className="mx-auto max-w-6xl p-6 lg:flex lg:min-h-dvh lg:items-center lg:p-16">
            <div className="flex flex-col gap-5 lg:w-full lg:flex-row lg:items-start lg:gap-16">
                <ProfilePhotoGallery profile={profile} photoUrl={photoUrl} backTo={backTo} backLabel={backLabel} />

                <div className="flex min-w-0 flex-1 flex-col gap-10">
                    <div className="flex flex-col gap-5">
                        <div className="flex flex-col gap-2">
                            <div className="flex items-center justify-between gap-4">
                                <OnlineStatus profile={profile} />
                                {topRight}
                            </div>
                            <ProfileHeader profile={profile} />
                        </div>
                        <ProfileMeta profile={profile} />
                        {actions}
                    </div>

                    <div className="h-px bg-grey/20" />

                    <ProfileAbout bio={profile.bio} />
                    <ProfileInterests tags={profile.tags} myTags={myTags} />
                </div>
            </div>
        </div>
    );
}
