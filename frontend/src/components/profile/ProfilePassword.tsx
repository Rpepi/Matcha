import { useProfilePassword } from "@/hooks/useProfilePassword";
import { Button, Field, FormNotice } from "@/components/FormControls";

export default function ProfilePassword({ username }: { username: string }) {
    const { isEditing, isSaving, current, setCurrent, next, setNext, formError, startEditing, cancelEditing, save } =
        useProfilePassword();

    return (
        <div className="flex flex-col gap-3">
            <div className="flex items-center justify-between">
                <h2 className="text-xs font-semibold tracking-widest text-grey uppercase">Password</h2>
                {!isEditing && (
                    <button
                        type="button"
                        onClick={startEditing}
                        className="cursor-pointer rounded-full px-2.5 py-1 text-sm font-medium text-grey transition hover:bg-grey/10 hover:text-ink"
                    >
                        Change
                    </button>
                )}
            </div>

            {!isEditing && <p className="text-ink">••••••••</p>}

            {isEditing && (
                <form
                    className="flex flex-col gap-3"
                    noValidate
                    onSubmit={(event) => {
                        event.preventDefault();
                        if (!isSaving) void save();
                    }}
                >
                    {/* Lets password managers know which account this is (and keeps Chrome from flagging the form). */}
                    <input type="text" name="username" autoComplete="username" value={username} readOnly hidden />
                    <Field
                        label="Current password"
                        id="current-password"
                        type="password"
                        autoComplete="current-password"
                        value={current}
                        onChange={(e) => setCurrent(e.target.value)}
                        required
                    />
                    <Field
                        label="New password"
                        id="new-password"
                        type="password"
                        autoComplete="new-password"
                        value={next}
                        onChange={(e) => setNext(e.target.value)}
                        required
                    />
                    <p className="text-sm text-grey">
                        At least 8 characters, not only letters or only digits, and not a common password.
                    </p>

                    <FormNotice>{formError}</FormNotice>

                    <div className="flex gap-3">
                        <Button type="submit" disabled={isSaving || !current || !next} className="w-auto px-4 py-2 text-sm">
                            {isSaving ? "Saving..." : "Change password"}
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
