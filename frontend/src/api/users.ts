export interface UserPhoto {
    position: number;
    path: string;
    is_profile: boolean;
}

export interface UserProfileDetail {
    id: number;
    username: string;
    first_name: string;
    last_name: string;
    gender: string | null;
    orientation: string | null;
    bio: string | null;
    birth_date: string | null;
    fame_rating: number;
    city: string | null;
    is_online: boolean;
    last_seen: string | null;
    photos: UserPhoto[];
    tags: string[];
    is_liked_by_me: boolean;
    is_match: boolean;
}

export async function getUserProfile(id: number): Promise<Response> {
    const response = await fetch(`/api/users/${id}`, {
        credentials: 'include',
    })
    return response
}
