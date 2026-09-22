import { useEffect, useState } from "react";

const BREAKPOINTS: { query: string; count: 1 | 3 | 5 }[] = [
    { query: "(min-width: 1280px)", count: 5 },
    { query: "(min-width: 768px)", count: 3 },
];

function getItemsPerScreen(): 1 | 3 | 5 {
    for (const { query, count } of BREAKPOINTS) {
        if (window.matchMedia(query).matches) return count;
    }
    return 1;
}

export function useItemsPerScreen(): 1 | 3 | 5 {
    const [itemsPerScreen, setItemsPerScreen] = useState<1 | 3 | 5>(getItemsPerScreen);

    useEffect(() => {
        const mediaQueries = BREAKPOINTS.map(({ query }) => window.matchMedia(query));
        const handleChange = () => setItemsPerScreen(getItemsPerScreen());

        mediaQueries.forEach((mq) => mq.addEventListener("change", handleChange));
        return () => mediaQueries.forEach((mq) => mq.removeEventListener("change", handleChange));
    }, []);

    return itemsPerScreen;
}
