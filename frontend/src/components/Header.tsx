import { Link } from "react-router-dom";
import { LogOut, X } from "lucide-react";
import logo from "../assets/logo.png";
import { Button } from "./FormControls";
import { useLogout } from "@/hooks/useLogout";

interface HeaderProps {
    /** `logout`: a signed-in page outside the app layout (profile setup), where log out replaces the close cross. */
    variant: "landing" | "close" | "logout";
}

function LogoutButton() {
    const handleLogout = useLogout();
    return (
        <button
            type="button"
            onClick={handleLogout}
            className="flex cursor-pointer items-center gap-2 rounded-full px-3 py-1.5 text-sm font-medium text-ink/60 transition hover:bg-grey/10 hover:text-ink"
        >
            <LogOut className="h-4 w-4" aria-hidden="true" />
            Log out
        </button>
    );
}

export default function Header({ variant }: HeaderProps) {
    const isLanding = variant === "landing";

    return (
        <header className="flex items-center justify-between px-6 py-6 sm:px-10">
            <Link
                to="/"
                className={`flex items-center gap-2 font-display text-3xl font-medium tracking-tight text-matcha`}
            >
                <img src={logo} alt="" className="h-10 w-10" />
                matcha
            </Link>

            {isLanding ? (
                <nav className="hidden items-center gap-5 sm:flex">
                    <Link
                        to="/login"
                        className="text-sm font-medium transition"
                    >
                        Log in
                    </Link>
                    <Link to="/register">
                        <Button className="w-auto rounded-full px-4 py-2 text-sm">
                            Sign up
                        </Button>
                    </Link>
                </nav>
            ) : variant === "logout" ? (
                <LogoutButton />
            ) : (
                <Link
                    to="/"
                    aria-label="Back to home"
                    className="text-ink/60 transition hover:text-ink"
                >
                    <X className="h-6 w-6" />
                </Link>
            )}
        </header>
    );
}
