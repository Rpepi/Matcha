import { useState } from "react";
import { Menu } from "@base-ui/react/menu";
import { AlertDialog } from "@base-ui/react/alert-dialog";
import { Ellipsis, Flag } from "lucide-react";
import { fieldClasses } from "@/components/FormControls";
import { useReport } from "@/hooks/useReport";

const focusClasses =
    "focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-matcha";

export default function ReportMenu({ userId, firstName }: { userId: number; firstName: string }) {
    const [dialogOpen, setDialogOpen] = useState(false);
    const [reason, setReason] = useState("");
    const { report, isReporting } = useReport(userId, firstName);

    async function handleConfirm() {
        const ok = await report(reason);
        if (ok) {
            setDialogOpen(false);
            setReason("");
        }
    }

    return (
        <>
            <Menu.Root>
                <Menu.Trigger
                    aria-label="More options"
                    className={`flex h-9 w-9 shrink-0 cursor-pointer items-center justify-center rounded-full text-grey transition hover:bg-grey/10 hover:text-ink ${focusClasses}`}
                >
                    <Ellipsis className="h-5 w-5" aria-hidden="true" />
                </Menu.Trigger>
                <Menu.Portal>
                    <Menu.Positioner side="bottom" align="end" sideOffset={6}>
                        <Menu.Popup className="min-w-40 rounded-xl bg-white p-1.5 shadow-lg shadow-ink/20 outline-none">
                            <Menu.Item
                                onClick={() => setDialogOpen(true)}
                                className="flex cursor-pointer items-center gap-2 rounded-lg px-3 py-2.5 text-sm font-medium text-pink outline-none transition data-[highlighted]:bg-pink/15"
                            >
                                <Flag className="h-4 w-4" aria-hidden="true" />
                                Report {firstName}
                            </Menu.Item>
                        </Menu.Popup>
                    </Menu.Positioner>
                </Menu.Portal>
            </Menu.Root>

            <AlertDialog.Root open={dialogOpen} onOpenChange={(next) => !isReporting && setDialogOpen(next)}>
                <AlertDialog.Portal>
                    <AlertDialog.Backdrop className="fixed inset-0 z-40 bg-ink/50 transition-opacity duration-150 data-[ending-style]:opacity-0 data-[starting-style]:opacity-0" />
                    <AlertDialog.Popup className="fixed top-1/2 left-1/2 z-40 w-[calc(100%-2.5rem)] max-w-md -translate-x-1/2 -translate-y-1/2 rounded-2xl bg-white p-6 shadow-xl shadow-ink/20 outline-none transition-all duration-150 data-[ending-style]:scale-95 data-[ending-style]:opacity-0 data-[starting-style]:scale-95 data-[starting-style]:opacity-0">
                        <AlertDialog.Title className="font-display text-xl font-medium text-ink">
                            Report {firstName}?
                        </AlertDialog.Title>
                        <AlertDialog.Description className="mt-3 text-sm text-grey">
                            Let us know what's wrong. This is optional, but it helps our review.
                        </AlertDialog.Description>

                        <textarea
                            value={reason}
                            onChange={(event) => setReason(event.target.value.slice(0, 500))}
                            placeholder="Reason (optional)"
                            rows={3}
                            maxLength={500}
                            className={`mt-4 resize-none ${fieldClasses}`}
                        />

                        <div className="mt-6 flex items-center justify-end gap-3">
                            <AlertDialog.Close
                                disabled={isReporting}
                                className="cursor-pointer rounded-xl px-4 py-2.5 text-sm font-medium text-grey transition hover:text-ink disabled:cursor-not-allowed disabled:opacity-60"
                            >
                                Cancel
                            </AlertDialog.Close>
                            <button
                                type="button"
                                onClick={handleConfirm}
                                disabled={isReporting}
                                className={`cursor-pointer rounded-xl bg-pink px-5 py-2.5 text-sm font-medium text-ink transition hover:brightness-95 disabled:cursor-not-allowed disabled:opacity-60 ${focusClasses}`}
                            >
                                {isReporting ? "Reporting…" : "Report"}
                            </button>
                        </div>
                    </AlertDialog.Popup>
                </AlertDialog.Portal>
            </AlertDialog.Root>
        </>
    );
}
