import { useState } from "react";
import { AlertDialog } from "@base-ui/react/alert-dialog";
import { Ban } from "lucide-react";

interface BlockButtonProps {
    name: string;
    /** Resolves true when the block went through. */
    onConfirm: () => Promise<boolean>;
    isBlocking: boolean;
    /** `icon`: round button for headers. `text`: labelled, for the profile page. */
    variant?: "icon" | "text";
    className?: string;
}

const focusClasses =
    "focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-matcha";

export default function BlockButton({ name, onConfirm, isBlocking, variant = "text", className = "" }: BlockButtonProps) {
    const [open, setOpen] = useState(false);

    async function handleConfirm() {
        await onConfirm();
        // Success navigates away; on failure a toast explains. Either way the dialog has done its job.
        setOpen(false);
    }

    return (
        <AlertDialog.Root open={open} onOpenChange={(next) => !isBlocking && setOpen(next)}>
            {variant === "icon" ? (
                <AlertDialog.Trigger
                    aria-label={`Block ${name}`}
                    className={`flex h-10 w-10 shrink-0 cursor-pointer items-center justify-center rounded-full text-grey transition hover:bg-pink/15 hover:text-ink ${focusClasses} ${className}`}
                >
                    <Ban className="h-5 w-5" aria-hidden="true" />
                </AlertDialog.Trigger>
            ) : (
                <AlertDialog.Trigger
                    className={`flex cursor-pointer items-center gap-2 rounded-full px-4 py-3 text-sm font-medium text-grey transition hover:bg-pink/15 hover:text-ink ${focusClasses} ${className}`}
                >
                    <Ban className="h-4 w-4" aria-hidden="true" />
                    Block
                    <span className="sr-only"> {name}</span>
                </AlertDialog.Trigger>
            )}

            <AlertDialog.Portal>
                <AlertDialog.Backdrop className="fixed inset-0 z-40 bg-ink/50 transition-opacity duration-150 data-[ending-style]:opacity-0 data-[starting-style]:opacity-0" />
                <AlertDialog.Popup className="fixed top-1/2 left-1/2 z-40 w-[calc(100%-2.5rem)] max-w-md -translate-x-1/2 -translate-y-1/2 rounded-2xl bg-white p-6 shadow-xl shadow-ink/20 outline-none transition-all duration-150 data-[ending-style]:scale-95 data-[ending-style]:opacity-0 data-[starting-style]:scale-95 data-[starting-style]:opacity-0">
                    <AlertDialog.Title className="font-display text-xl font-medium text-ink">
                        Block {name}?
                    </AlertDialog.Title>
                    <AlertDialog.Description className="mt-3 text-sm text-grey">
                        You won't see each other anymore. Any like or match between you is removed and your conversation
                        closes. {name} won't be notified.
                    </AlertDialog.Description>

                    <div className="mt-6 flex items-center justify-end gap-3">
                        <AlertDialog.Close
                            disabled={isBlocking}
                            className="cursor-pointer rounded-xl px-4 py-2.5 text-sm font-medium text-grey transition hover:text-ink disabled:cursor-not-allowed disabled:opacity-60"
                        >
                            Cancel
                        </AlertDialog.Close>
                        <button
                            type="button"
                            onClick={handleConfirm}
                            disabled={isBlocking}
                            className={`cursor-pointer rounded-xl bg-pink px-5 py-2.5 text-sm font-medium text-ink transition hover:brightness-95 disabled:cursor-not-allowed disabled:opacity-60 ${focusClasses}`}
                        >
                            {isBlocking ? "Blocking…" : "Block"}
                        </button>
                    </div>
                </AlertDialog.Popup>
            </AlertDialog.Portal>
        </AlertDialog.Root>
    );
}
