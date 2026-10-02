import { AnimatePresence, motion } from "motion/react";
import { useLocation, useOutlet } from "react-router-dom";
import { pageFadeVariants } from "@/lib/pageTransition";

export default function AnimatedOutlet() {
    const location = useLocation();
    const element = useOutlet();

    return (
        <AnimatePresence mode="wait" initial={false}>
            <motion.div
                key={location.pathname}
                variants={pageFadeVariants}
                initial="initial"
                animate="animate"
                exit="exit"
            >
                {element}
            </motion.div>
        </AnimatePresence>
    );
}
