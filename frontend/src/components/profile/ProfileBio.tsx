import { useState } from "react";
import { useProfileContext } from "@/context/ProfileContext";
import { useToast } from "@/context/ToastContext";
import { updateProfile } from "@/api/profile";
import { Button } from "@/components/FormControls";

export default function ProfileBio({ bio }: { bio: string | null }) {
    const { refetch } = useProfileContext();
    const { showError } = useToast();
    const [isEditing, setIsEditing] = useState(false);
    const [isSaving, setIsSaving] = useState(false);
    const [draft, setDraft] = useState(bio ?? "");

    function startEditing() {
        setDraft(bio ?? "");
        setIsEditing(true);
    }

    async function save() {
        setIsSaving(true);
        const response = await updateProfile({ bio: draft });
        setIsSaving(false);
        if (!response.ok) {
            const data = await response.json().catch(() => null);
            showError(data?.detail ?? "Could not save your bio. Please try again.");
            return;
        }
        await refetch();
        setIsEditing(false);
    }

    return (
        <div className="flex flex-col gap-3">
            <div className="flex items-center justify-between">
                <h2 className="text-xs font-semibold tracking-widest text-grey uppercase">About</h2>
                {!isEditing && (
                    <button
                        type="button"
                        onClick={startEditing}
                        className="cursor-pointer rounded-full px-2.5 py-1 text-sm font-medium text-grey transition hover:bg-grey/10 hover:text-ink"
                    >
                        Edit
                    </button>
                )}
            </div>

            {isEditing ? (
                <div className="flex flex-col gap-3">
                    <textarea
                        value={draft}
                        onChange={(e) => setDraft(e.target.value)}
                        rows={4}
                        placeholder="A line about you"
                        className="w-full resize-none rounded-xl border border-grey/30 bg-paper px-4 py-2.5 text-ink outline-none transition placeholder:text-ink/40 focus:ring-2 focus:ring-grey/30"
                    />
                    <div className="flex gap-3">
                        <Button onClick={save} disabled={isSaving} className="w-auto px-4 py-2 text-sm">
                            {isSaving ? "Saving..." : "Save"}
                        </Button>
                        <button
                            type="button"
                            onClick={() => setIsEditing(false)}
                            disabled={isSaving}
                            className="cursor-pointer rounded-xl px-4 py-2 text-sm font-medium text-ink/70 transition hover:bg-grey/10 disabled:cursor-not-allowed disabled:opacity-60"
                        >
                            Cancel
                        </button>
                    </div>
                </div>
            ) : (
                <p className={`max-w-xl text-lg leading-relaxed ${bio ? "text-ink/90" : "text-grey/50 italic"}`}>
                    {bio || "Empty"}
                </p>
            )}
        </div>
    );
}
