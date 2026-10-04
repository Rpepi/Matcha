export async function likeUser(id: number): Promise<Response> {
    const response = await fetch(`/api/users/${id}/like`, {
        method: 'POST',
        credentials: 'include',
    })
    return response
}

export async function unlikeUser(id: number): Promise<Response> {
    const response = await fetch(`/api/users/${id}/like`, {
        method: 'DELETE',
        credentials: 'include',
    })
    return response
}
