export const STAGGER_SECONDS = 0;
export const SLIDE_SECONDS = 0.4;
export const EXIT_EXTRA_DELAY_SECONDS = 0.1;

export function transitionDurationMs(cardCount: number): number {
    return (cardCount - 1) * STAGGER_SECONDS * 1000 + EXIT_EXTRA_DELAY_SECONDS * 1000 + SLIDE_SECONDS * 1000;
}

export const cardVariants = {
    hidden: {
        y: "100vh",
        opacity: 0,
    },
    visible: (i: number) => ({
        y: 0,
        opacity: 1,
        transition: { delay: i * STAGGER_SECONDS, duration: SLIDE_SECONDS, ease: "easeOut" as const },
    }),
    exit: (i: number) => ({
        y: "-100vh",
        opacity: 0,
        transition: { delay: i * STAGGER_SECONDS + EXIT_EXTRA_DELAY_SECONDS, duration: SLIDE_SECONDS },
    }),
};
