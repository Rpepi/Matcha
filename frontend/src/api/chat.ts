export const MAX_MESSAGE_LENGTH = 1000;

export interface ChatUser {
    id: number;
    first_name: string;
    is_online: boolean;
    last_seen: string | null;
    photo: string | null;
}

export interface ChatMessage {
    id: number;
    sender_id: number;
    content: string;
    created_at: string;
}

export interface Conversation {
    user: ChatUser;
    last_message: ChatMessage | null;
    unread_count: number;
}

export interface MessagePage {
    messages: ChatMessage[];
    has_more: boolean;
}

export async function getConversations(): Promise<Response> {
    const response = await fetch('/api/chat/conversations', {
        credentials: 'include',
    })
    return response
}

export async function getMessages(
    targetId: number,
    { before, limit }: { before?: number; limit?: number } = {},
): Promise<Response> {
    const params = new URLSearchParams();
    if (before !== undefined) params.set('before', String(before));
    if (limit !== undefined) params.set('limit', String(limit));
    const query = params.size > 0 ? `?${params.toString()}` : '';

    const response = await fetch(`/api/chat/${targetId}/messages${query}`, {
        credentials: 'include',
    })
    return response
}

export async function markSeen(targetId: number): Promise<Response> {
    const response = await fetch(`/api/chat/${targetId}/seen`, {
        method: 'POST',
        credentials: 'include',
    })
    return response
}

/** Same-origin WebSocket URL: goes through the Vite `/api` proxy (`ws: true`). */
export function chatSocketUrl(targetId: number): string {
    const scheme = window.location.protocol === 'https:' ? 'wss' : 'ws';
    return `${scheme}://${window.location.host}/api/chat/${targetId}`;
}

/** `photo` is a backend path such as `/users/12/photos/1`. */
export function photoSrc(photo: string): string {
    return `/api${photo}`;
}
