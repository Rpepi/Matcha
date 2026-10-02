export interface BrowseFilters {
    minAge: number;
    maxAge: number;
    maxDistance: number;
    minFame: number;
    minTags: number;
}

export const AGE_MIN = 18;
export const AGE_MAX = 99;
export const DISTANCE_MAX_KM = 200;
export const FAME_MAX = 100;
export const TAGS_MAX = 5;

export const DEFAULT_FILTERS: BrowseFilters = {
    minAge: AGE_MIN,
    maxAge: AGE_MAX,
    maxDistance: DISTANCE_MAX_KM,
    minFame: 0,
    minTags: 0,
};
