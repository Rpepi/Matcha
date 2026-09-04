import { useState, useEffect, type ReactNode } from "react"
import { Navigate } from "react-router-dom"

type Status = 'loading' | 'auth' | 'unauth'

export default function ProtectedRoute({ children }: { children: ReactNode })
{
    const [status, setStatus] = useState<Status>('loading')

    useEffect(() => {
        fetch('/api/auth/me', { credentials: 'include' })
            .then(res => setStatus(res.ok ? 'auth' : 'unauth'))
            .catch(() => setStatus('unauth'))
    }, [])

    if (status === 'loading') return <p>Loading...</p>
    if (status === 'unauth') return <Navigate to="/login" />
    return children
}
