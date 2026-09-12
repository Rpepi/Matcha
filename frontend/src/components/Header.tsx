import { Link } from "react-router-dom";
import { X } from "lucide-react";
import logo from "../assets/logo.png";

interface HeaderProps {
    variant: "landing" | "close";
}

export default function Header({ variant }: HeaderProps) {
    const isLanding = variant === "landing";

    return (
        <header className="flex items-center justify-between px-6 py-6 sm:px-10">
            <Link
                to="/"
                className={`flex items-center gap-2 font-display text-xl font-medium tracking-tight ${
                    isLanding ? "text-petal" : "text-plum"
                }`}
            >
                <img src={logo} alt="" className="h-7 w-7" />
                matcha
            </Link>

            {isLanding ? (
                <nav className="flex items-center gap-5">
                    <Link
                        to="/login"
                        className="text-sm font-medium text-petal/70 transition hover:text-petal"
                    >
                        Log in
                    </Link>
                    <Link
                        to="/register"
                        className="rounded-full bg-gradient-to-r from-garnet to-orchid px-4 py-2 text-sm font-medium text-petal shadow-lg shadow-garnet/25 transition hover:brightness-110"
                    >
                        Create an account
                    </Link>
                </nav>
            ) : (
                <Link
                    to="/"
                    aria-label="Back to home"
                    className="text-plum/60 transition hover:text-plum"
                >
                    <X className="h-6 w-6" />
                </Link>
            )}
        </header>
    );
}
