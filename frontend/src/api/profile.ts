export async function updateProfile(fields: Partial<{
    username: string;
    first_name: string;
    last_name: string;
    gender: string;
    orientation: string;
    bio: string;
    birth_date: string;
    city: string | null;
}>): Promise<Response> {
    const response = await fetch('/api/profile/me', {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        credentials: 'include',
        body: JSON.stringify(fields),
    })
    return response
}

export async function updateLocation(latitude: number, longitude: number): Promise<Response> {
    const response = await fetch('/api/profile/location', {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        credentials: 'include',
        body: JSON.stringify({ latitude, longitude }),
    })
    return response
}
