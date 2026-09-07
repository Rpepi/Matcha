import { Dialog } from "@base-ui/react/dialog";
import { GradientButton } from "./FormControls";

interface ErrorPopupProps {
    open: boolean;
    onOpenChange: (open: boolean) => void;
    message?: string;
}

const DEFAULT_MESSAGE =
    "Something went wrong. Please try again in a moment.";

export default function ErrorPopup({ open, onOpenChange, message }: ErrorPopupProps) {
    return (
        <Dialog.Root open={open} onOpenChange={onOpenChange}>
            <Dialog.Portal>
                <Dialog.Backdrop className="fixed inset-0 bg-ink/50 transition-opacity duration-150 data-[ending-style]:opacity-0 data-[starting-style]:opacity-0" />
                <Dialog.Popup className="fixed top-1/2 left-1/2 w-[calc(100%-2.5rem)] max-w-sm -translate-x-1/2 -translate-y-1/2 rounded-2xl bg-white p-6 text-center shadow-xl shadow-ink/20 outline-none transition-all duration-150 data-[ending-style]:scale-95 data-[ending-style]:opacity-0 data-[starting-style]:scale-95 data-[starting-style]:opacity-0">
                    <Dialog.Title className="font-display text-xl font-medium text-plum">
                        We hit a snag
                    </Dialog.Title>
                    <Dialog.Description className="mt-2 text-sm text-plum/60">
                        {message ?? DEFAULT_MESSAGE}
                    </Dialog.Description>
                    <Dialog.Close
                        render={
                            <GradientButton className="mt-6" type="button" />
                        }
                    >
                        Got it
                    </Dialog.Close>
                </Dialog.Popup>
            </Dialog.Portal>
        </Dialog.Root>
    );
}
