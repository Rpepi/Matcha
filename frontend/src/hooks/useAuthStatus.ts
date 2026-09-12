import { useState, useEffect } from "react";

export type AuthStatus = 'loading' | 'guest' | 'incomplete' | 'complete';

export function useAuthStatus(): AuthStatus {
    const [status, setStatus] = useState<AuthStatus>('loading');

    useEffect(() => {
        fetch('/api/profile/me', { credentials: 'include' })
            .then(async (res) => {
                if (!res.ok) {
                    setStatus('guest');
                    return;
                }
                const data = await res.json();
                setStatus(data.profile_complete ? 'complete' : 'incomplete');
            })
            .catch(() => setStatus('guest'));
    }, []);

    return status;
}
