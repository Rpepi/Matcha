import { MapPin } from "lucide-react";

function capitalize(value: string): string {
    return value.charAt(0).toUpperCase() + value.slice(1);
}

interface ProfileMetaProps {
    profile: {
        gender: string | null;
        city: string | null;
    };
}

export default function ProfileMeta({ profile }: ProfileMetaProps) {
    return (
        <div className="flex flex-wrap items-center gap-3 text-ink/80">
            {profile.gender && <span>{capitalize(profile.gender)}</span>}

            {profile.gender && profile.city && <span className="h-1 w-1 rounded-full bg-grey/50" />}

            {profile.city && (
                <span className="flex items-center gap-1.5">
                    <MapPin className="h-4 w-4" aria-hidden="true" />
                    {profile.city}
                </span>
            )}
        </div>
    );
}
