export default function ProfileInterests({ tags, myTags }: { tags: string[]; myTags: string[] }) {
    if (tags.length === 0) return null;

    const mySet = new Set(myTags);

    return (
        <div className="flex flex-col gap-3">
            <h2 className="text-xs font-semibold tracking-widest text-grey uppercase">Interests</h2>
            <ul className="flex max-w-xl flex-wrap gap-2.5">
                {tags.map((tag) => {
                    const shared = mySet.has(tag);
                    return (
                        <li
                            key={tag}
                            className={`flex items-center gap-1.5 rounded-full px-4 py-2 text-sm font-medium ${
                                shared ? "bg-matcha text-matcha-dark" : "bg-grey/10 text-ink/80"
                            }`}
                        >
                            {tag}
                            {shared && <span className="sr-only"> (shared interest)</span>}
                        </li>
                    );
                })}
            </ul>
        </div>
    );
}
