import type { ReactNode } from "react";
import type { Profile } from "@/context/ProfileContext";
import { useProfileDetails } from "@/hooks/useProfileDetails";
import { Button } from "@/components/FormControls";

const GENDERS = ["male", "female", "other"];
const ORIENTATIONS = ["hetero", "homo", "bi"];

const inputClasses =
    "w-full rounded-lg border border-grey/30 bg-paper px-2.5 py-1 text-right text-sm text-ink outline-none transition focus:ring-2 focus:ring-grey/30";

function capitalize(value: string): string {
    return value.charAt(0).toUpperCase() + value.slice(1);
}

function formatDate(value: string): string {
    return new Date(value).toLocaleDateString(undefined, { year: "numeric", month: "long", day: "numeric" });
}

function Field({ label, value, input }: { label: string; value: string | null; input?: ReactNode }) {
    return (
        <div className="flex flex-1 items-center justify-between gap-4">
            <span className="shrink-0 whitespace-nowrap text-sm font-medium text-grey">{label}</span>
            {input ? (
                <div className="min-w-0 flex-1">{input}</div>
            ) : (
                <span className={`text-right ${value ? "text-ink" : "text-grey/50"}`}>{value ?? "Not set"}</span>
            )}
        </div>
    );
}

function Row({ label, value, input }: { label: string; value: string | null; input?: ReactNode }) {
    return (
        <div className="py-3">
            <Field label={label} value={value} input={input} />
        </div>
    );
}

function DualRow({
    left,
    right,
}: {
    left: { label: string; value: string | null; input?: ReactNode };
    right: { label: string; value: string | null; input?: ReactNode };
}) {
    return (
        <div className="flex flex-col gap-3 py-3 sm:flex-row sm:items-center sm:gap-6">
            <Field label={left.label} value={left.value} input={left.input} />
            <Field label={right.label} value={right.value} input={right.input} />
        </div>
    );
}

export default function ProfileDetails({ profile }: { profile: Profile }) {
    const { isEditing, isSaving, fields, startEditing, cancelEditing, setField, save } = useProfileDetails(profile);

    return (
        <div className="flex flex-col divide-y divide-grey/10">
            <div className="flex items-center justify-between pb-3">
                <h2 className="text-xs font-semibold tracking-widest text-grey uppercase">Personal info</h2>
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

            <DualRow
                left={{
                    label: "First name",
                    value: profile.first_name,
                    input: isEditing && (
                        <input
                            className={inputClasses}
                            value={fields.first_name}
                            onChange={(e) => setField("first_name", e.target.value)}
                        />
                    ),
                }}
                right={{
                    label: "Last name",
                    value: profile.last_name,
                    input: isEditing && (
                        <input
                            className={inputClasses}
                            value={fields.last_name}
                            onChange={(e) => setField("last_name", e.target.value)}
                        />
                    ),
                }}
            />
            <Row label="Email" value={profile.email} />
            <Row
                label="Gender"
                value={profile.gender ? capitalize(profile.gender) : null}
                input={
                    isEditing && (
                        <select
                            className={inputClasses}
                            value={fields.gender}
                            onChange={(e) => setField("gender", e.target.value)}
                        >
                            <option value="" disabled>
                                Choose one
                            </option>
                            {GENDERS.map((g) => (
                                <option key={g} value={g}>
                                    {capitalize(g)}
                                </option>
                            ))}
                        </select>
                    )
                }
            />
            <Row
                label="Interested in"
                value={profile.orientation ? capitalize(profile.orientation) : null}
                input={
                    isEditing && (
                        <select
                            className={inputClasses}
                            value={fields.orientation}
                            onChange={(e) => setField("orientation", e.target.value)}
                        >
                            <option value="" disabled>
                                Choose one
                            </option>
                            {ORIENTATIONS.map((o) => (
                                <option key={o} value={o}>
                                    {capitalize(o)}
                                </option>
                            ))}
                        </select>
                    )
                }
            />
            <Row
                label="Birth date"
                value={profile.birth_date ? formatDate(profile.birth_date) : null}
                input={
                    isEditing && (
                        <input
                            type="date"
                            className={inputClasses}
                            value={fields.birth_date}
                            onChange={(e) => setField("birth_date", e.target.value)}
                        />
                    )
                }
            />
            {isEditing && (
                <div className="flex gap-3 pt-4">
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
            )}
        </div>
    );
}
