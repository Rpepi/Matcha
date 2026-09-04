import { Link } from "react-router-dom";
import PhotoStack from "../components/PhotoStack";
import { GradientButton } from "../components/FormControls";
import { Avatar, AvatarFallback, AvatarImage } from "@/components/ui/avatar"
import { Bubble, BubbleContent } from "@/components/ui/bubble"

import { Message, MessageAvatar, MessageContent, MessageHeader } from "@/components/ui/message"
import avatar1 from "../assets/avatar1.jpg"
import avatar2 from "../assets/avatar2.jpg"


interface Step {
    label: string
    title: string
    body: string
}



const steps: Step[] = [
    {
        label: "One",
        title: "Set up your profile",
        body: "Gender, orientation, a bio, up to five photos and a few tags — takes about five minutes.",
    },
    {
        label: "Two",
        title: "See who's nearby",
        body: "Suggestions are ranked by distance, shared tags and popularity — not random.",
    },
    {
        label: "Three",
        title: "Chat when it's mutual",
        body: "Liking is one-sided. Chatting only unlocks once you've both liked each other.",
    },
];

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

                    <PhotoStack
                        className="shrink-0"
                        frontSlot={
                            <div className="flex h-full flex-col justify-end gap-2.5 p-5">
                                <Message>
                                    <MessageAvatar>
                                        <Avatar >
                                            <AvatarImage src={avatar1} alt="Lea" />
                                            <AvatarFallback className="bg-gradient-to-br from-orchid to-bloom text-petal">
                                                L
                                            </AvatarFallback>
                                        </Avatar>
                                    </MessageAvatar>
                                    <MessageContent>
                                        <MessageHeader>Lea</MessageHeader>
                                        <Bubble className="*:data-[slot=bubble-content]:bg-white/12">
                                            <BubbleContent className="text-petal">
                                            ok what's your type
                                            </BubbleContent>
                                        </Bubble>
                                        
                                    </MessageContent>
                                </Message>
                                <Message align="end">
                                    <MessageAvatar>
                                        <Avatar>
                                            <AvatarImage src={avatar2} alt="You" />
                                            <AvatarFallback className="bg-gradient-to-br from-garnet to-orchid text-petal">
                                                Y
                                            </AvatarFallback>
                                        </Avatar>
                                    </MessageAvatar>
                                    <MessageContent>
                                        <Bubble align="end">
                                            <BubbleContent className="bg-gradient-to-br from-ink to-orchid text-petal">
                                                people who open with "what's your type"
                                            </BubbleContent>
                                        </Bubble>
                                    </MessageContent>
                                </Message>
                                <Message>
                                    <MessageAvatar>
                                        <Avatar>
                                            <AvatarImage src={avatar1} alt="Lea" />
                                            <AvatarFallback className="bg-gradient-to-br from-orchid to-bloom text-petal">
                                                L
                                            </AvatarFallback>
                                        </Avatar>
                                    </MessageAvatar>
                                    <MessageContent>
                                        <MessageHeader>Lea</MessageHeader>
                                        <Bubble className="*:data-[slot=bubble-content]:bg-white/12">
                                            <BubbleContent className="text-petal">
                                                oh no. i'm already into you
                                            </BubbleContent>
                                        </Bubble>
                                    </MessageContent>
                                </Message>
                            </div>
                        }
                    />
                </section>

                <section className="bg-petal py-20 text-plum">
                    <div className="mx-auto max-w-6xl px-6 sm:px-10">
                        <h2 className="font-display text-3xl font-medium">
                            How it works
                        </h2>
                        <div className="mt-10 grid gap-10 sm:grid-cols-3">
                            {steps.map((step) => (
                                <div key={step.title}>
                                    <p className="font-display text-lg italic text-orchid">
                                        {step.label}
                                    </p>
                                    <h3 className="mt-2 text-lg font-semibold">
                                        {step.title}
                                    </h3>
                                    <p className="mt-2 text-sm text-plum/60">{step.body}</p>
                                </div>
                            ))}
                        </div>
                    </div>
                </section>
            </main>

            <footer className="border-t border-petal/10 px-6 py-8 sm:px-10">
                <div className="mx-auto flex max-w-6xl flex-col items-center justify-between gap-3 text-sm text-petal/50 sm:flex-row">
                    <span className="font-display text-base text-petal/80">matcha</span>
                    <p>Built for the 42 Matcha project.</p>
                    <div className="flex items-center gap-4">
                        <Link to="/login" className="hover:text-petal">
                            Log in
                        </Link>
                        <Link to="/register" className="hover:text-petal">
                            Register
                        </Link>
                    </div>
                </div>
            </footer>
        </div>
    );
}
