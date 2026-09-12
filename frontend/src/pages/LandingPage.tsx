import { Link } from "react-router-dom";
import { GradientButton } from "../components/FormControls";

export default function LandingPage() {
    return (
        <div className="flex min-h-screen flex-col bg-ink font-sans text-petal">
            <header className="flex items-center justify-between px-6 py-6 sm:px-10">
                <span className="font-display text-xl font-medium tracking-tight">
                    matcha
                </span>
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
            </header>

            <main className="flex-1">
                <section className="mx-auto flex max-w-6xl flex-col items-center gap-14 px-6 py-14 sm:px-10 lg:flex-row lg:items-center lg:justify-between lg:py-24">
                    <div className="max-w-xl text-center lg:text-left">
                        <p className="mb-4 text-sm font-medium tracking-wide text-bloom">
                            Matcha · Meet nearby
                        </p>
                        <h1 className="font-display text-5xl leading-[1.05] font-medium text-balance sm:text-6xl">
                            Meet people who already like you back.
                        </h1>
                        <p className="mt-5 text-lg text-petal/70">
                            Real profiles nearby, matched on interests you actually share —
                            not just a swipe.
                        </p>
                        <div className="mt-8 flex flex-col items-center gap-3 sm:flex-row lg:justify-start">
                            <Link to="/register" className="w-full sm:w-auto">
                                <GradientButton className="w-full px-6 sm:w-auto">
                                    Create an account
                                </GradientButton>
                            </Link>
                            <div className="flex flex-col">
                                <p>Already a member?</p>
                                <Link
                                    to="/login"
                                    className="text-sm font-medium text-petal/70 transition text-center hover:text-petal"
                                >
                                log in
                                </Link>
                            </div>
                        </div>
                    </div>
                </section>
            </main>
        </div>
    );
}
