import { useProfileBio } from "@/hooks/useProfileBio";
import { Button, fieldClasses } from "@/components/FormControls";

const MAX_BIO_LENGTH = 500;

export default function ProfileBio({ bio }: { bio: string | null }) {
    const { isEditing, isSaving, draft, setDraft, startEditing, cancelEditing, save } = useProfileBio(bio);

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
                        onChange={(e) => setDraft(e.target.value.slice(0, MAX_BIO_LENGTH))}
                        rows={4}
                        maxLength={MAX_BIO_LENGTH}
                        placeholder="A line about you"
                        className={`${fieldClasses} resize-none`}
                    />
                    <span className="self-end text-xs text-grey/50">
                        {draft.length}/{MAX_BIO_LENGTH}
                    </span>
                    <div className="flex gap-3">
                        <Button onClick={save} disabled={isSaving} className="w-auto px-4 py-2 text-sm">
                            {isSaving ? "Saving..." : "Save"}
                        </Button>
                        <button
                            type="button"
                            onClick={cancelEditing}
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
