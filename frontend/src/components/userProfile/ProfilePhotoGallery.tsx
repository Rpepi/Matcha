import { useState } from "react";
import { Link } from "react-router-dom";
import { ArrowLeft, ChevronLeft, ChevronRight } from "lucide-react";
import type { UserProfileDetail } from "@/api/users";
import { placeholderPhotoUrl } from "@/lib/placeholderPhoto";

const buttonClasses =
    "flex h-11 w-11 shrink-0 cursor-pointer items-center justify-center rounded-full bg-paper/90 text-ink transition hover:bg-paper focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-matcha";

export default function ProfilePhotoGallery({ profile }: { profile: UserProfileDetail }) {
    const [index, setIndex] = useState(0);
    const photos = profile.photos;
    const count = photos.length || 1;

    function goTo(next: number) {
        setIndex(((next % count) + count) % count);
    }

    const src =
        photos.length > 0
            ? `/api/users/${profile.id}/photos/${photos[index].position}?v=${encodeURIComponent(photos[index].path)}`
            : placeholderPhotoUrl(profile.id);

    return (
        <section
            aria-label={`Photos of ${profile.first_name}`}
            className="relative h-[55vh] max-h-[520px] w-full flex-shrink-0 overflow-hidden rounded-[32px] bg-grey/10 lg:h-auto lg:aspect-[3/4] lg:w-[42%]"
        >
            <img src={src} alt="" className="h-full w-full object-cover" />

            <div className="absolute inset-x-4 top-4 flex items-center gap-3">
                <Link to="/browse" aria-label="Back to Browse" className={buttonClasses}>
                    <ArrowLeft className="h-5 w-5" />
                </Link>
            </div>

            <div className="absolute inset-x-4 bottom-4 flex flex-col gap-3">
                {photos.length > 1 && (
                    <div
                        className="mx-auto grid w-[140px] gap-1"
                        style={{ gridTemplateColumns: `repeat(${photos.length}, minmax(0, 1fr))` }}
                    >
                        {photos.map((photo, i) => (
                            <div
                                key={photo.position}
                                className={`h-1 rounded-full ${i === index ? "bg-paper" : "bg-paper/45"}`}
                            />
                        ))}
                    </div>
                )}

                {profile.is_online && (
                    <div className="flex items-center gap-2 self-start rounded-full bg-paper/90 px-3 py-1.5 text-sm font-medium text-ink">
                        <span className="h-2 w-2 rounded-full bg-matcha" />
                        Active now
                    </div>
                )}
            </div>

            {photos.length > 1 && (
                <>
                    <button
                        type="button"
                        onClick={() => goTo(index - 1)}
                        aria-label="Previous photo"
                        className={`absolute left-4 top-1/2 -translate-y-1/2 ${buttonClasses}`}
                    >
                        <ChevronLeft className="h-5 w-5" />
                    </button>
                    <button
                        type="button"
                        onClick={() => goTo(index + 1)}
                        aria-label="Next photo"
                        className={`absolute right-4 top-1/2 -translate-y-1/2 ${buttonClasses}`}
                    >
                        <ChevronRight className="h-5 w-5" />
                    </button>
                </>
            )}
        </section>
    );
}
