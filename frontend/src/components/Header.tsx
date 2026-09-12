import { Link } from "react-router-dom";
import { X } from "lucide-react";
import logo from "../assets/logo.png";
import { Button } from "./FormControls";

interface HeaderProps {
    variant: "landing" | "close";
}

export default function Header({ variant }: HeaderProps) {
    const isLanding = variant === "landing";

    return (
        <header className="flex items-center justify-between px-6 py-6 sm:px-10">
            <Link
                to="/"
                className={`flex items-center gap-2 font-display text-xl font-medium tracking-tight text-matcha`}
            >
                <img src={logo} alt="" className="h-7 w-7" />
                matcha
            </Link>

            {isLanding ? (
                <nav className="flex items-center gap-5">
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
