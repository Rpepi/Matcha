import { useState, type ReactNode } from "react";
import type { Profile } from "@/context/ProfileContext";
import { useProfileContext } from "@/context/ProfileContext";
import { useToast } from "@/context/ToastContext";
import { updateProfile } from "@/api/profile";
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

interface EditableFields {
    first_name: string;
    last_name: string;
    gender: string;
    orientation: string;
    birth_date: string;
}

function fieldsFrom(profile: Profile): EditableFields {
    return {
        first_name: profile.first_name,
        last_name: profile.last_name,
        gender: profile.gender ?? "",
        orientation: profile.orientation ?? "",
        birth_date: profile.birth_date ?? "",
    };
}

export default function ProfileDetails({ profile }: { profile: Profile }) {
    const { refetch } = useProfileContext();
    const { showError } = useToast();
    const [isEditing, setIsEditing] = useState(false);
    const [isSaving, setIsSaving] = useState(false);
    const [fields, setFields] = useState<EditableFields>(() => fieldsFrom(profile));

    function startEditing() {
        setFields(fieldsFrom(profile));
        setIsEditing(true);
    }

    function set<K extends keyof EditableFields>(key: K, value: EditableFields[K]) {
        setFields((prev) => ({ ...prev, [key]: value }));
    }

    async function save() {
        setIsSaving(true);
        const response = await updateProfile(fields);
        setIsSaving(false);
        if (!response.ok) {
            const data = await response.json().catch(() => null);
            showError(data?.detail ?? "Could not save your profile. Please try again.");
            return;
        }
        await refetch();
        setIsEditing(false);
    }

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
                            onChange={(e) => set("first_name", e.target.value)}
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
                            onChange={(e) => set("last_name", e.target.value)}
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
                            onChange={(e) => set("gender", e.target.value)}
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
                            onChange={(e) => set("orientation", e.target.value)}
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
                            onChange={(e) => set("birth_date", e.target.value)}
                        />
                    )
                }
            />
            <Row label="City" value={profile.city} />

            {isEditing && (
                <div className="flex gap-3 pt-4">
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
            )}
        </div>
    );
}
