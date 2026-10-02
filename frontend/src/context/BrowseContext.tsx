import { createContext, useContext, type ReactNode } from "react";
import { useBrowseProfiles } from "@/hooks/useBrowseProfiles";
import { useItemsPerScreen } from "@/hooks/useItemsPerScreen";
import type { BrowseProfile } from "@/api/browse";
import type { BrowseFilters } from "@/lib/browseFilters";

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
}

const BrowseContext = createContext<BrowseContextValue | undefined>(undefined);

export function BrowseProvider({ children }: { children: ReactNode }) {
    const itemsPerScreen = useItemsPerScreen();
    const { profiles, cursor, advance, isLoading, error, atEnd, filters, applyFilters } = useBrowseProfiles(itemsPerScreen);

    return (
        <BrowseContext.Provider
            value={{ itemsPerScreen, profiles, cursor, advance, isLoading, error, atEnd, filters, applyFilters }}
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
