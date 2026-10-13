import { Fragment, type ReactNode } from "react";
import { MapPin } from "lucide-react";
import { orientationLabel } from "@/lib/orientation";

function capitalize(value: string): string {
    return value.charAt(0).toUpperCase() + value.slice(1);
}

interface ProfileMetaProps {
    profile: {
        gender: string | null;
        orientation: string | null;
        city: string | null;
        /** From the viewer; absent on one's own preview. */
        distance_km?: number | null;
    };
}

export default function ProfileMeta({ profile }: ProfileMetaProps) {
    const items: ReactNode[] = [];
    if (profile.gender) items.push(capitalize(profile.gender));
    // No orientation given counts as bisexual (the subject's rule), so it is always shown.
    items.push(orientationLabel(profile.orientation, profile.gender));
    if (profile.city) {
        items.push(
            <span className="flex items-center gap-1.5">
                <MapPin className="h-4 w-4" aria-hidden="true" />
                {profile.city}
            </span>,
        );
    }
    if (profile.distance_km != null) items.push(`${profile.distance_km} km away`);

    return (
        <div className="flex flex-wrap items-center gap-3 text-ink/80">
            {items.map((item, i) => (
                <Fragment key={i}>
                    {i > 0 && <span className="h-1 w-1 rounded-full bg-grey/50" aria-hidden="true" />}
                    <span>{item}</span>
                </Fragment>
            ))}
        </div>
    );
}
