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

export async function getBrowseProfiles(page: number): Promise<Response> {
    const response = await fetch(`/api/users?page=${page}`, {
        credentials: 'include',
    })
    return response
}
