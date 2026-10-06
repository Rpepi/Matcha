import { useCallback, useRef, useState } from "react";
import { likeUser, unlikeUser } from "@/api/likes";
import { useBrowseContext, type LikeState } from "@/context/BrowseContext";
import { useProfileContext } from "@/context/ProfileContext";
import { useToast } from "@/context/ToastContext";

export const NO_PICTURE_MESSAGE = "Add a profile picture to your profile to like people.";

function describeFailure(response: Response, liking: boolean): string {
    if (response.status === 429) return "You're doing that too fast. Please wait a moment and try again.";

    // The server refuses a like from someone with no profile picture of their own.
    if (response.status === 403 && liking) return NO_PICTURE_MESSAGE;

    if (response.status === 404 && liking) return "This profile is no longer available.";

    return liking ? "Could not like this profile. Please try again." : "Could not remove your like. Please try again.";
}

/**
 * Like / unlike one user. The heart flips immediately and goes back if the
 * server refuses. `server` is what the page knew when it loaded; anything the
 * user did since is in the shared browse context and wins.
 *
 * Liking needs a profile picture of one's own. Without one, the server is known
 * to refuse, so liking explains why straight away, without flipping the heart or
 * spending a request from the rate-limit budget. Unliking is always allowed.
 */
export function useLike(userId: number, firstName: string, server: LikeState) {
    const { likes, setLike } = useBrowseContext();
    const { profile, refetch: refetchProfile } = useProfileContext();
    const canLike = profile?.photos.some((photo) => photo.is_profile) ?? false;
    const { showError, showNotice } = useToast();
    const [isPending, setIsPending] = useState(false);
    const inFlight = useRef(false);

    const state = likes[userId] ?? server;

    const toggle = useCallback(async () => {
        if (inFlight.current) return; // a double click must not send two opposite requests
        if (!state.liked && !canLike) {
            showError(NO_PICTURE_MESSAGE);
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
            showError(describeFailure(response, liking));
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
