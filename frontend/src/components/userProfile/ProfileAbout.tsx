interface ProfileAboutProps {
    bio: string | null;
    emptyText?: string;
}

export default function ProfileAbout({ bio, emptyText }: ProfileAboutProps) {
    if (!bio && !emptyText) return null;

    return (
        <div className="flex flex-col gap-3">
            <h2 className="text-xs font-semibold tracking-widest text-grey uppercase">About</h2>
            <p className={`max-w-xl text-lg leading-relaxed ${bio ? "text-ink/90" : "text-grey/50 italic"}`}>
                {bio || emptyText}
            </p>
        </div>
    );
}
