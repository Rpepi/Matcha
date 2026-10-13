import type { Profile } from "@/context/ProfileContext";
import { useProfileEmail } from "@/hooks/useProfileEmail";
import { Button, Field, FormNotice } from "@/components/FormControls";

const linkButtonClasses =
    "cursor-pointer rounded-full px-3 py-1 text-sm font-medium text-ink transition hover:bg-grey/10 disabled:cursor-not-allowed disabled:opacity-60";

export default function ProfileEmail({ profile }: { profile: Pick<Profile, "email" | "pending_email" | "auth_provider"> }) {
    const { isEditing, isSaving, isBusy, draft, setDraft, formError, startEditing, cancelEditing, save, resend, cancelPending } =
        useProfileEmail(profile);
    const canChange = profile.auth_provider === "email";

    return (
        <div className="flex flex-col gap-3">
            <div className="flex items-center justify-between">
                <h2 className="text-xs font-semibold tracking-widest text-grey uppercase">Email</h2>
                {canChange && !isEditing && (
                    <button
                        type="button"
                        onClick={startEditing}
                        className="cursor-pointer rounded-full px-2.5 py-1 text-sm font-medium text-grey transition hover:bg-grey/10 hover:text-ink"
                    >
                        Edit
                    </button>
                )}
            </div>

            <p className="break-all text-ink">{profile.email}</p>

            {!canChange && <p className="text-sm text-grey">This account signs in with Google, so its email can't be changed here.</p>}

            {profile.pending_email && !isEditing && (
                <div className="flex flex-col gap-2">
                    <FormNotice tone="info">
                        Waiting for you to confirm <strong className="break-all">{profile.pending_email}</strong>. Your current email stays active until you click the link we sent.
                    </FormNotice>
                    <div className="flex gap-2">
                        <button type="button" onClick={resend} disabled={isBusy} className={linkButtonClasses}>
                            Resend link
                        </button>
                        <button type="button" onClick={cancelPending} disabled={isBusy} className={linkButtonClasses}>
                            Cancel change
                        </button>
                    </div>
                </div>
            )}

            {isEditing && (
                <form
                    className="flex flex-col gap-3"
                    noValidate
                    onSubmit={(event) => {
                        event.preventDefault();
                        if (!isSaving) void save();
                    }}
                >
                    <Field
                        label="New email"
                        id="new-email"
                        name="email"
                        type="email"
                        autoComplete="email"
                        maxLength={100}
                        value={draft}
                        onChange={(e) => setDraft(e.target.value)}
                        required
                    />
                    <p className="text-sm text-grey">
                        We'll send a confirmation link to the new address. Your current email keeps working until you click it.
                    </p>

                    <FormNotice>{formError}</FormNotice>

                    <div className="flex gap-3">
                        <Button type="submit" disabled={isSaving || !draft.trim()} className="w-auto px-4 py-2 text-sm">
                            {isSaving ? "Sending..." : "Send confirmation link"}
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
                </form>
            )}
        </div>
    );
}
