export async function updateProfile(fields: Partial<{
    email: string;
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

export interface Visit {
    id: number;
    visitor_id: number;
    created_at: string;
    first_name: string;
    photo_position: number | null;
}

export interface Like {
    id: number;
    liker_id: number;
    created_at: string;
    first_name: string;
    photo_position: number | null;
}

export async function getVisits(): Promise<Response> {
    const response = await fetch('/api/profile/me/visits', {
        credentials: 'include',
    })
    return response
}

export async function getLikes(): Promise<Response> {
    const response = await fetch('/api/profile/me/likes', {
        credentials: 'include',
    })
    return response
}

/** Drops the email change waiting for its confirmation link; the current email stays. */
export async function cancelPendingEmail(): Promise<Response> {
    const response = await fetch('/api/profile/pending-email', {
        method: 'DELETE',
        credentials: 'include',
    })
    return response
}

/** Mails the confirmation link of the pending email again (shares a 5-per-hour budget with changing it). */
export async function resendPendingEmail(): Promise<Response> {
    const response = await fetch('/api/profile/pending-email/resend', {
        method: 'POST',
        credentials: 'include',
    })
    return response
}
