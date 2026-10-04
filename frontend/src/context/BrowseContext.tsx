import { createContext, useCallback, useContext, useState, type ReactNode } from "react";
import { useBrowseProfiles } from "@/hooks/useBrowseProfiles";
import { useItemsPerScreen } from "@/hooks/useItemsPerScreen";
import type { BrowseProfile } from "@/api/browse";
import type { BrowseFilters } from "@/lib/browseFilters";

export interface LikeState {
    liked: boolean;
    match: boolean;
}

interface BrowseContextValue {
    itemsPerScreen: 1 | 3 | 4 | 5;
    profiles: BrowseProfile[];
    cursor: number;
    advance: () => void;
    isLoading: boolean;
    error: string | null;
    atEnd: boolean;
    filters: BrowseFilters;
    applyFilters: (next: BrowseFilters) => void;
    removeProfile: (userId: number) => void;
    /** Likes changed during this visit, by user id. Wins over what the server sent. */
    likes: Record<number, LikeState>;
    setLike: (userId: number, state: LikeState) => void;
}

const BrowseContext = createContext<BrowseContextValue | undefined>(undefined);

export function BrowseProvider({ children }: { children: ReactNode }) {
    const itemsPerScreen = useItemsPerScreen();
    const { profiles, cursor, advance, isLoading, error, atEnd, filters, applyFilters, removeProfile } = useBrowseProfiles(itemsPerScreen);

    // A card unmounts as soon as it scrolls out, and the user page is another
    // route: the like state lives here so both always agree.
    const [likes, setLikes] = useState<Record<number, LikeState>>({});
    const setLike = useCallback((userId: number, state: LikeState) => {
        setLikes((prev) => ({ ...prev, [userId]: state }));
    }, []);

    return (
        <BrowseContext.Provider
            value={{ itemsPerScreen, profiles, cursor, advance, isLoading, error, atEnd, filters, applyFilters, removeProfile, likes, setLike }}
        >
            {children}
        </BrowseContext.Provider>
    );
}

export function useBrowseContext(): BrowseContextValue {
    const ctx = useContext(BrowseContext);
    if (!ctx) throw new Error("useBrowseContext must be used within a BrowseProvider");
    return ctx;
}
