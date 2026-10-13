import type { ReactNode } from "react"
import Header from "./Header";

interface AuthLayoutProps {
    children: ReactNode
    /** Signed-in page (profile setup): offer to log out instead of the close cross. */
    showLogout?: boolean
}

export default function AuthLayout({ children, showLogout }: AuthLayoutProps) {
    return (
        <div className="min-h-screen font-sans">
            <Header variant={showLogout ? "logout" : "close"} />
            <div className="flex items-center justify-center px-6 py-10 sm:px-10">
                <div className="w-full max-w-sm">{children}</div>
            </div>
        </div>
    );
}
