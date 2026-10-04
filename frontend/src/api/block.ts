export async function blockUser(id: number): Promise<Response> {
    const response = await fetch(`/api/users/${id}/block`, {
        method: 'POST',
        credentials: 'include',
    })
    return response
}
