import type { ReactNode } from "react"
import Header from "./Header";

interface AuthLayoutProps {
    children: ReactNode
    hideClose?: boolean
}

export default function AuthLayout({ children, hideClose }: AuthLayoutProps) {
    return (
        <div className="min-h-screen font-sans">
            <Header variant="close" hideClose={hideClose} />
            <div className="flex items-center justify-center px-6 py-10 sm:px-10">
                <div className="w-full max-w-sm">{children}</div>
            </div>
        </div>
    );
}
