export type BrowseSort = "score" | "age" | "distance" | "fame" | "tags";
export type SortOrder = "asc" | "desc";

export interface BrowseFilters {
    minAge: number;
    maxAge: number;
    maxDistance: number;
    minFame: number;
    maxFame: number;
    /** Minimum number of tags in common with the current user. */
    minTags: number;
    /** Tags every profile must carry (chosen by name, whatever the current user's own tags are). */
    tags: string[];
    sort: BrowseSort;
    order: SortOrder;
}

export const AGE_MIN = 16;
export const AGE_MAX = 99;
export const DISTANCE_MAX_KM = 200;
export const FAME_MAX = 100;
export const TAGS_MAX = 5;
/** Same cap as the API: at most 5 named tags per search. */
export const NAMED_TAGS_MAX = 5;

/** What each sort is called, which way it goes unless told otherwise, and how each way reads. */
export const SORT_OPTIONS: Record<BrowseSort, { label: string; defaultOrder: SortOrder; asc: string; desc: string }> = {
    score: { label: "Best match", defaultOrder: "desc", asc: "Worst match first", desc: "Best match first" },
    age: { label: "Age", defaultOrder: "asc", asc: "Youngest first", desc: "Oldest first" },
    distance: { label: "Distance", defaultOrder: "asc", asc: "Closest first", desc: "Farthest first" },
    fame: { label: "Fame rating", defaultOrder: "desc", asc: "Lowest first", desc: "Highest first" },
    tags: { label: "Shared interests", defaultOrder: "desc", asc: "Fewest first", desc: "Most first" },
};

export const DEFAULT_FILTERS: BrowseFilters = {
    minAge: AGE_MIN,
    maxAge: AGE_MAX,
    maxDistance: DISTANCE_MAX_KM,
    minFame: 0,
    maxFame: FAME_MAX,
    minTags: 0,
    tags: [],
    sort: "score",
    order: SORT_OPTIONS.score.defaultOrder,
};
