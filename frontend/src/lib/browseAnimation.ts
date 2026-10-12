export const STAGGER_SECONDS = 0;
export const SLIDE_SECONDS = 0.4;
export const EXIT_EXTRA_DELAY_SECONDS = 0.1;

export interface CardMotion {
    index?: number;
    direction: 1 | -1;
}

export const cardVariants = {
    hidden: ({ direction }: CardMotion) => ({
        x: direction > 0 ? "100vw" : "-100vw",
        opacity: 1,
    }),
    visible: ({ index = 0 }: CardMotion) => ({
        x: 0,
        opacity: 1,
        transition: { delay: index * STAGGER_SECONDS, duration: SLIDE_SECONDS, ease: "easeOut" as const },
    }),
    exit: ({ index = 0, direction }: CardMotion) => ({
        x: direction > 0 ? "-100vw" : "100vw",
        opacity: 1,
        transition: { delay: index * STAGGER_SECONDS + EXIT_EXTRA_DELAY_SECONDS, duration: SLIDE_SECONDS },
    }),
};

export function transitionDurationMs(cardCount: number): number {
    const { delay, duration } = cardVariants.exit({ index: cardCount - 1, direction: 1 }).transition;
    return (delay + duration) * 1000;
}
