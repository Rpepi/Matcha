export const PAGE_FADE_SECONDS = 0.2;

export const pageFadeVariants = {
    initial: { opacity: 0 },
    animate: { opacity: 1, transition: { duration: PAGE_FADE_SECONDS, ease: "easeOut" as const } },
    exit: { opacity: 0, transition: { duration: PAGE_FADE_SECONDS, ease: "easeIn" as const } },
};
