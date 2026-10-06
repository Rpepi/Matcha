import { MapPin } from "lucide-react";

function capitalize(value: string): string {
    return value.charAt(0).toUpperCase() + value.slice(1);
}

interface ProfileMetaProps {
    profile: {
        gender: string | null;
        city: string | null;
        is_online: boolean;
    };
}

export default function ProfileMeta({ profile }: ProfileMetaProps) {
    const hasMeta = profile.gender || profile.city;

    return (
        <div className="flex flex-wrap items-center gap-3 text-ink/80">
            <div className="flex items-center gap-2 text-sm font-medium">
                <span className={`h-2 w-2 rounded-full ${profile.is_online ? "bg-matcha" : "bg-grey/50"}`} />
                {profile.is_online ? "Active now" : "Offline"}
            </div>

            {hasMeta && <span className="h-1 w-1 rounded-full bg-grey/50" />}

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
