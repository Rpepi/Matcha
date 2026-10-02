export const STAGGER_SECONDS = 0;
export const SLIDE_SECONDS = 0.4;
export const EXIT_EXTRA_DELAY_SECONDS = 0.1;

export const cardVariants = {
    hidden: {
        x: "100vw",
        opacity: 1,
    },
    visible: (i: number) => ({
        x: 0,
        opacity: 1,
        transition: { delay: i * STAGGER_SECONDS, duration: SLIDE_SECONDS, ease: "easeOut" as const },
    }),
    exit: (i: number) => ({
        x: "-100vw",
        opacity: 1,
        transition: { delay: i * STAGGER_SECONDS + EXIT_EXTRA_DELAY_SECONDS, duration: SLIDE_SECONDS },
    }),
};

export function transitionDurationMs(cardCount: number): number {
    const { delay, duration } = cardVariants.exit(cardCount - 1).transition;
    return (delay + duration) * 1000;
}
