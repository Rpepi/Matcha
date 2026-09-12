import type { ReactNode } from "react"
import { Navigate } from "react-router-dom"
import { useAuthStatus } from "../hooks/useAuthStatus"

export default function OnboardingRoute({ children }: { children: ReactNode })
{
    const status = useAuthStatus()

    if (status === 'loading') return null
    if (status === 'guest') return <Navigate to="/login" />
    if (status === 'complete') return <Navigate to="/browse" />
    return children
}
