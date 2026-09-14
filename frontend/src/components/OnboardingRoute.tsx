import type { ReactNode } from "react"
import { Navigate } from "react-router-dom"
import { useAuthStatus } from "../hooks/useAuthStatus"
import LoadingScreen from "./LoadingScreen"

export default function OnboardingRoute({ children }: { children: ReactNode })
{
    const status = useAuthStatus()

    if (status === 'loading') return <LoadingScreen />
    if (status === 'guest') return <Navigate to="/login" />
    if (status === 'complete') return <Navigate to="/browse" />
    return children
}
