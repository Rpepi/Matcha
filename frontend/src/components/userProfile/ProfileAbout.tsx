export default function ProfileAbout({ bio }: { bio: string | null }) {
    if (!bio) return null;

    return (
        <div className="flex flex-col gap-3">
            <h2 className="text-xs font-semibold tracking-widest text-grey uppercase">About</h2>
            <p className="max-w-xl text-lg leading-relaxed text-ink/90">{bio}</p>
        </div>
    );
}
