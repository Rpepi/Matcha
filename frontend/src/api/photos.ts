export async function uploadPhoto(file: File): Promise<Response> {
    const formData = new FormData();
    formData.append('photos', file);
    const response = await fetch('/api/profile/photos', {
        method: 'POST',
        credentials: 'include',
        body: formData,
    })
    return response
}

export async function deletePhoto(position: number): Promise<Response> {
    const response = await fetch(`/api/profile/photos/${position}`, {
        method: 'DELETE',
        credentials: 'include',
    })
    return response
}

export async function movePhoto(from: number, to: number): Promise<Response> {
    const response = await fetch(`/api/profile/photos/${from}/move`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        credentials: 'include',
        body: JSON.stringify({ to }),
    })
    return response
}
