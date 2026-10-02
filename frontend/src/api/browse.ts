import { DEFAULT_FILTERS, type BrowseFilters } from "../lib/browseFilters";

export interface BrowseProfile {
    id: number;
    first_name: string;
    last_name: string;
    gender: string | null;
    bio: string | null;
    birth_date: string | null;
    fame_rating: number;
    city: string | null;
    is_online: boolean;
    last_seen: string | null;
    age: number | null;
    distance_km: number | null;
    common_tags: number;
    score: number;
    photo: string | null;
}

export async function getBrowseProfiles(page: number, filters: BrowseFilters = DEFAULT_FILTERS): Promise<Response> {
    const params = new URLSearchParams({ page: String(page) });
    if (filters.minAge !== DEFAULT_FILTERS.minAge) params.set('min_age', String(filters.minAge));
    if (filters.maxAge !== DEFAULT_FILTERS.maxAge) params.set('max_age', String(filters.maxAge));
    if (filters.maxDistance !== DEFAULT_FILTERS.maxDistance) params.set('max_distance', String(filters.maxDistance));
    if (filters.minFame !== DEFAULT_FILTERS.minFame) params.set('min_fame', String(filters.minFame));
    if (filters.minTags !== DEFAULT_FILTERS.minTags) params.set('min_tags', String(filters.minTags));

    const response = await fetch(`/api/users?${params.toString()}`, {
        credentials: 'include',
    })
    return response
}
