export interface AppNotification {
    id: number
    type: "like" | "visit" | "message" | "match" | "unlike"
    seen: boolean
    created_at: string
    from_user_id: number
    first_name: string
}

export interface UnreadNotificationCount {
    unread: number
}


export async function getNotification(): Promise<Response> {
    const response = await fetch(`/api/notifications`, {
        credentials: 'include',
    })
    return response
}


export async function markNotificationSeen(): Promise<Response> {
    const response = await fetch(`/api/notifications/seen`, {
        method: 'POST',
        credentials: 'include',
    })
    return response
}


export async function getUnreadCount(): Promise<Response> {
    const response = await fetch(`/api/notifications/unread-count`, {
        credentials: 'include',
    })
    return response
}
