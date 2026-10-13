import { useRef, useState } from "react";
import { Link } from "react-router-dom";
import { Button } from "../components/FormControls";
import Header from "../components/Header";
import MatchaPowder from "../components/landing/MatchaPowder";

export default function LandingPage() {
    const [ctaActive, setCtaActive] = useState(false);
    const taglineRef = useRef<HTMLParagraphElement>(null);

    return (
        // The powder covers the whole page, header included; everything else sits on top of it
        <div className="relative flex min-h-screen flex-col overflow-hidden bg-paper font-sans">
            <MatchaPowder active={ctaActive} belowRef={taglineRef} />
            <div className="relative">
                <Header variant="landing" />
            </div>
            <main className="flex-1">
                <section className="relative mx-auto flex max-w-6xl flex-col items-center gap-14 px-6 py-14 sm:px-10 lg:items-center lg:justify-between lg:py-24">
                    <div className="max-w-xl text-center">
                        <h1 className="font-display text-4xl leading-[1.05] font-medium text-balance sm:text-6xl">
                            Someone&nbsp;out&nbsp;there matches you.
                        </h1>
                        {/* The background sits on an inline span so each line only covers its own words */}
                        <p ref={taglineRef} className="mt-5 text-lg leading-[2.1] text-grey">
                            <span className="box-decoration-clone rounded-xl bg-paper px-3 py-1.5">
                                Real profiles nearby, matched on interests you actually share —
                                not just a swipe.
                            </span>
                        </p>
                        <div className="mt-8 flex flex-col items-center">
                            <Link to="/register" className="w-full sm:w-auto">
                                <Button
                                    className="w-full px-6 sm:w-auto"
                                    onPointerEnter={() => setCtaActive(true)}
                                    onPointerLeave={() => setCtaActive(false)}
                                    onFocus={() => setCtaActive(true)}
                                    onBlur={() => setCtaActive(false)}
                                >
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
