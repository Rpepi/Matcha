export async function reportUser(id: number, reason: string | null): Promise<Response> {
    const response = await fetch(`/api/users/${id}/report`, {
        method: 'POST',
        credentials: 'include',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ reason }),
    })
    return response
}
