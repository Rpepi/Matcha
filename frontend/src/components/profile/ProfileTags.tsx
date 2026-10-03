export default function ProfileTags({ tags }: { tags: string[] }) {
    if (tags.length === 0) return null;

    return (
        <div className="flex flex-col gap-3">
            <h2 className="text-xs font-semibold tracking-widest text-grey uppercase">Interests</h2>
            <ul className="flex max-w-xl flex-wrap gap-2.5">
                {tags.map((tag) => (
                    <li key={tag} className="rounded-full bg-matcha text-matcha-dark px-4 py-2 text-sm font-medium">
                        {tag}
                    </li>
                ))}
            </ul>
        </div>
    );
}
