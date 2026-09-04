import type { ReactNode } from "react"
import { Link } from "react-router-dom";
import PhotoStack from "./PhotoStack";

interface AuthLayoutProps {
    eyebrow?: string
    headline: ReactNode
    tagline?: string
    frontSlot?: ReactNode
    children: ReactNode
}

export default function AuthLayout({
    eyebrow,
    headline,
    tagline,
    frontSlot,
    children,
}: AuthLayoutProps) {
    return (
        <div className="min-h-screen bg-ink font-sans text-petal lg:flex">
            <div className="relative flex flex-col justify-between overflow-hidden bg-gradient-to-br from-ink via-[#3a1030] to-garnet px-8 py-10 sm:px-14 sm:py-14 lg:w-1/2 lg:px-16">
                <Link
                    to="/"
                    className="font-display text-xl font-medium tracking-tight text-petal"
                >
                    matcha
                </Link>

                <div className="my-12 flex flex-1 items-center justify-center lg:my-0">
                    <PhotoStack frontSlot={frontSlot} />
                </div>

                <div className="max-w-sm">
                    {eyebrow && (
                        <p className="mb-3 text-sm font-medium tracking-wide text-bloom">
                            {eyebrow}
                        </p>
                    )}
                    <h1 className="font-display text-4xl leading-[1.05] font-medium text-balance sm:text-5xl">
                        {headline}
                    </h1>
                    {tagline && (
                        <p className="mt-4 text-base text-petal/70">{tagline}</p>
                    )}
                </div>
            </div>

            <div className="flex flex-1 items-center justify-center bg-petal px-6 py-14 sm:px-10 lg:w-1/2">
                <div className="w-full max-w-sm">{children}</div>
            </div>
        </div>
    );
}
