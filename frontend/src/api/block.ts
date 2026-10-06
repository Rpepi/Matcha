export interface BlockedUser {
    id: number;
    first_name: string;
    created_at: string;
}

export async function blockUser(id: number): Promise<Response> {
    const response = await fetch(`/api/users/${id}/block`, {
        method: 'POST',
        credentials: 'include',
    })
    return response
}

export async function unblockUser(id: number): Promise<Response> {
    const response = await fetch(`/api/users/${id}/block`, {
        method: 'DELETE',
        credentials: 'include',
    })
    return response
}

export async function getBlockedUsers(): Promise<Response> {
    const response = await fetch('/api/profile/me/blocked', {
        credentials: 'include',
    })
    return response
}
