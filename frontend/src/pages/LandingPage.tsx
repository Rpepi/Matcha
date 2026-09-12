import { Link } from "react-router-dom";
import { Button } from "../components/FormControls";
import Header from "../components/Header";

export default function LandingPage() {
    return (
        <div className="flex min-h-screen flex-col bg-paper font-sans">
            <Header variant="landing" />
            <main className="flex-1">
                <section className="mx-auto flex max-w-6xl flex-col items-center gap-14 px-6 py-14 sm:px-10 lg:items-center lg:justify-between lg:py-24">
                    <div className="max-w-xl text-center">
                        <h1 className="font-display text-5xl leading-[1.05] font-medium text-balance sm:text-6xl">
                            Someone out there matches you.
                        </h1>
                        <p className="mt-5 text-lg text-grey">
                            Real profiles nearby, matched on interests you actually share —
                            not just a swipe.
                        </p>
                        <div className="mt-8 flex flex-col items-center">
                            <Link to="/register" className="w-full sm:w-auto">
                                <Button className="w-full px-6 sm:w-auto">
                                    Start Matching
                                </Button>
                            </Link>
                        </div>
                    </div>
                </section>
            </main>
        </div>
    );
}
