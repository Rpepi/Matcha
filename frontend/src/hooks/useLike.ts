import { useCallback, useRef, useState } from "react";
import { likeUser, unlikeUser } from "@/api/likes";
import { useBrowseContext, type LikeState } from "@/context/BrowseContext";
import { useProfileContext } from "@/context/ProfileContext";
import { useToast } from "@/context/ToastContext";

export function noPictureMessage(firstName: string): string {
    return `${firstName} hasn't added a profile picture yet, so you can't like them.`;
}

async function describeFailure(response: Response, liking: boolean, firstName: string): Promise<string> {
    if (response.status === 429) return "You're doing that too fast. Please wait a moment and try again.";

    if (response.status === 404 && liking) {
        const data = await response.json().catch(() => null);
        const detail = typeof data?.detail === "string" ? data.detail : "";
        return detail.includes("profile picture") ? noPictureMessage(firstName) : "This profile is no longer available.";
    }

    return liking ? "Could not like this profile. Please try again." : "Could not remove your like. Please try again.";
}

/**
 * Like / unlike one user. The heart flips immediately and goes back if the
 * server refuses. `server` is what the page knew when it loaded; anything the
 * user did since is in the shared browse context and wins.
 *
 * `canLike` false means the server is known to refuse (no profile picture):
 * liking then explains why straight away, without flipping the heart or
 * spending a request from the rate-limit budget. Unliking is always allowed.
 */
export function useLike(userId: number, firstName: string, server: LikeState, canLike = true) {
    const { likes, setLike } = useBrowseContext();
    const { refetch: refetchProfile } = useProfileContext();
    const { showError, showNotice } = useToast();
    const [isPending, setIsPending] = useState(false);
    const inFlight = useRef(false);

    const state = likes[userId] ?? server;

    const toggle = useCallback(async () => {
        if (inFlight.current) return; // a double click must not send two opposite requests
        if (!state.liked && !canLike) {
            showError(noPictureMessage(firstName));
            return;
        }
        inFlight.current = true;
        setIsPending(true);

        const previous = state;
        const liking = !previous.liked;
        setLike(userId, { liked: liking, match: liking ? previous.match : false });

        try {
            const response = await (liking ? likeUser(userId) : unlikeUser(userId));

            if (response.ok) {
                if (liking) {
                    const data = await response.json().catch(() => null);
                    const isMatch = data?.message === "match";
                    // "already liked" says nothing about a match: keep what we knew.
                    setLike(userId, { liked: true, match: isMatch || previous.match });
                    if (isMatch) showNotice(`It's a match with ${firstName}!`);
                }
                return;
            }

            if (response.status === 401) {
                void refetchProfile(); // session expired: the route guard sends the user to /login
                setLike(userId, previous);
                return;
            }
            // Unliking something already gone: the state the user wanted is reached.
            if (!liking && response.status === 404) return;

            setLike(userId, previous);
            showError(await describeFailure(response, liking, firstName));
        } catch {
            setLike(userId, previous);
            showError("Network error. Check your connection and try again.");
        } finally {
            inFlight.current = false;
            setIsPending(false);
        }
    }, [state, canLike, userId, firstName, setLike, refetchProfile, showError, showNotice]);

    return { liked: state.liked, isMatch: state.match, isPending, canLike: canLike || state.liked, toggle };
}
