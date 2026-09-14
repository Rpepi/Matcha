export async function updateTags(tags: string[]): Promise<Response> {
    const response = await fetch('/api/profile/tags', {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        credentials: 'include',
        body: JSON.stringify({ tags }),
    })
    return response
}
