/** Shown instead of a photo when a user has none (or it fails to load). */
export default function PhotoFallback({ name }: { name: string }) {
    const initial = ([...name.trim()][0] ?? "?").toUpperCase();

    return (
        <div
            aria-hidden="true"
            className="flex h-full w-full items-center justify-center bg-matcha/25 font-display text-8xl font-medium text-ink/70"
        >
            {initial}
        </div>
    );
}
