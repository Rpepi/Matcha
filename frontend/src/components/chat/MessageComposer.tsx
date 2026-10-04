import { useEffect, useRef, type KeyboardEvent } from "react";
import { SendHorizontal } from "lucide-react";
import { MAX_MESSAGE_LENGTH } from "@/api/chat";

const MAX_HEIGHT_PX = 160;
const COUNTER_FROM = Math.floor(MAX_MESSAGE_LENGTH * 0.8);

interface MessageComposerProps {
    value: string;
    onChange: (value: string) => void;
    onSubmit: () => void;
    /** False while the socket is not open: the draft stays editable, sending waits. */
    isConnected: boolean;
    partnerName: string;
}

/** The backend counts characters (code points), `String.length` counts UTF-16 units. */
function countCharacters(text: string): number {
    return [...text].length;
}

export default function MessageComposer({ value, onChange, onSubmit, isConnected, partnerName }: MessageComposerProps) {
    const textareaRef = useRef<HTMLTextAreaElement>(null);
    const count = countCharacters(value);
    const tooLong = count > MAX_MESSAGE_LENGTH;
    const canSend = isConnected && value.trim().length > 0 && !tooLong;

    // Grow with the text, up to a cap.
    useEffect(() => {
        const el = textareaRef.current;
        if (!el) return;
        el.style.height = "auto";
        el.style.height = `${Math.min(el.scrollHeight, MAX_HEIGHT_PX)}px`;
    }, [value]);

    // Desktop: ready to type as soon as a conversation opens. Not on touch
    // screens, where it would pop the keyboard over the messages.
    useEffect(() => {
        if (window.matchMedia("(hover: hover) and (pointer: fine)").matches) textareaRef.current?.focus();
    }, [partnerName]);

    function handleKeyDown(event: KeyboardEvent<HTMLTextAreaElement>) {
        if (event.key !== "Enter" || event.shiftKey || event.nativeEvent.isComposing) return;
        // On a touch keyboard Enter is a line break; the button sends.
        if (window.matchMedia("(pointer: coarse)").matches) return;
        event.preventDefault();
        if (canSend) onSubmit();
    }

    return (
        <form
            onSubmit={(event) => {
                event.preventDefault();
                if (canSend) onSubmit();
            }}
            className="border-t-3 border-grey/15 bg-paper px-4 py-3 md:px-6"
        >
            <div className="flex items-end gap-3">
                <textarea
                    ref={textareaRef}
                    value={value}
                    onChange={(event) => onChange(event.target.value)}
                    onKeyDown={handleKeyDown}
                    rows={1}
                    aria-label={`Message to ${partnerName}`}
                    placeholder="Write a message"
                    className="min-h-[44px] w-full resize-none rounded-3xl border border-grey/30 bg-transparent px-5 py-2.5 text-[15px] leading-snug text-ink outline-none transition placeholder:text-ink/40 focus:ring-2 focus:ring-grey/30"
                />
                <button
                    type="submit"
                    disabled={!canSend}
                    aria-label="Send message"
                    className="flex h-11 w-11 shrink-0 cursor-pointer items-center justify-center rounded-full bg-matcha text-ink transition hover:brightness-95 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-matcha disabled:cursor-not-allowed disabled:opacity-50"
                >
                    <SendHorizontal className="h-5 w-5" />
                </button>
            </div>

            {count >= COUNTER_FROM && (
                <p className={`mt-1.5 pr-14 text-right text-xs ${tooLong ? "font-medium text-pink" : "text-grey"}`}>
                    {count} / {MAX_MESSAGE_LENGTH}
                </p>
            )}
        </form>
    );
}
