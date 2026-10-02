import { AnimatePresence, motion } from "motion/react";
import type { ToastState, ToastVariant } from "../context/ToastContext";

const VARIANT_CLASSES: Record<ToastVariant, string> = {
    error: "border-pink text-pink",
    notice: "border-matcha text-matcha",
};

export default function Toast({ toast, onDismiss }: { toast: ToastState | null; onDismiss: () => void }) {
    return (
        <div className="pointer-events-none fixed inset-x-0 top-6 z-50 flex justify-center px-4">
            <AnimatePresence>
                {toast && (
                    <motion.button
                        key={toast.id}
                        type="button"
                        onClick={onDismiss}
                        initial={{ y: -20, opacity: 0 }}
                        animate={{ y: 0, opacity: 1 }}
                        exit={{ y: -20, opacity: 0 }}
                        transition={{ duration: 0.2 }}
                        className={`pointer-events-auto max-w-sm cursor-pointer rounded-full border bg-ink px-5 py-3 text-left text-sm font-medium shadow-lg shadow-ink/20 ${VARIANT_CLASSES[toast.variant]}`}
                    >
                        {toast.message}
                    </motion.button>
                )}
            </AnimatePresence>
        </div>
    );
}
