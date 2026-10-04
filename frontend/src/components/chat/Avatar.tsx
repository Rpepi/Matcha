import { useState } from "react";
import { photoSrc, type ChatUser } from "@/api/chat";

interface AvatarProps {
    user: ChatUser;
    size?: number;
    showStatus?: boolean;
}

export default function Avatar({ user, size = 48, showStatus = false }: AvatarProps) {
    const [failedSrc, setFailedSrc] = useState<string | null>(null);
    const src = user.photo ? photoSrc(user.photo) : null;
    const showImage = src !== null && failedSrc !== src;
    const initial = ([...user.first_name.trim()][0] ?? "?").toUpperCase();

    return (
        <span className="relative inline-flex shrink-0" style={{ width: size, height: size }}>
            {showImage ? (
                <img
                    src={src}
                    alt=""
                    onError={() => setFailedSrc(src)}
                    className="h-full w-full rounded-full bg-grey/10 object-cover"
                />
            ) : (
                <span
                    aria-hidden="true"
                    className="flex h-full w-full items-center justify-center rounded-full bg-matcha/25 font-display font-medium text-ink"
                    style={{ fontSize: size * 0.4 }}
                >
                    {initial}
                </span>
            )}
            {showStatus && user.is_online && (
                <span className="absolute right-0 bottom-0 h-3 w-3 rounded-full bg-matcha ring-2 ring-paper" />
            )}
        </span>
    );
}
