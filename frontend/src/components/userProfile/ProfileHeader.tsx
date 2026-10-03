import { Flame } from "lucide-react";
import { calculateAge } from "@/lib/age";
import { popularityScore } from "@/lib/popularity";

interface ProfileHeaderProps {
    profile: {
        first_name: string;
        birth_date: string | null;
        fame_rating: number;
    };
}

export default function ProfileHeader({ profile }: ProfileHeaderProps) {
    const age = profile.birth_date ? calculateAge(profile.birth_date) : null;

    return (
        <div className="flex items-center justify-between gap-4">
            <h1 className="min-w-0 truncate font-display text-5xl font-semibold text-ink lg:text-6xl">
                {profile.first_name}
                {age !== null && <span className="text-grey">, {age}</span>}
            </h1>

            <div className="flex shrink-0 items-center gap-1.5 rounded-full bg-matcha/15 px-4 py-2">
                <Flame className="h-4 w-4 fill-current text-matcha-dark" aria-hidden="true" />
                <span className="sr-only">Popularity</span>
                <span className="font-medium text-ink">{popularityScore(profile.fame_rating)}</span>
            </div>
        </div>
    );
}
