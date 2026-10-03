import type { Profile } from "@/context/ProfileContext";

function capitalize(value: string): string {
    return value.charAt(0).toUpperCase() + value.slice(1);
}

function formatDate(value: string): string {
    return new Date(value).toLocaleDateString(undefined, { year: "numeric", month: "long", day: "numeric" });
}

function Field({ label, value }: { label: string; value: string | null }) {
    return (
        <div className="flex flex-1 items-center justify-between gap-4">
            <span className="text-sm font-medium text-grey">{label}</span>
            <span className={`text-right ${value ? "text-ink" : "text-grey/50"}`}>{value ?? "Not set"}</span>
        </div>
    );
}

function Row({ label, value }: { label: string; value: string | null }) {
    return (
        <div className="py-3">
            <Field label={label} value={value} />
        </div>
    );
}

function DualRow({
    left,
    right,
}: {
    left: { label: string; value: string | null };
    right: { label: string; value: string | null };
}) {
    return (
        <div className="flex gap-6 py-3">
            <Field label={left.label} value={left.value} />
            <Field label={right.label} value={right.value} />
        </div>
    );
}

export default function ProfileDetails({ profile }: { profile: Profile }) {
    return (
        <div className="flex flex-col divide-y divide-grey/10">
            <DualRow
                left={{ label: "First name", value: profile.first_name }}
                right={{ label: "Last name", value: profile.last_name }}
            />
            <Row label="Email" value={profile.email} />
            <Row label="Gender" value={profile.gender ? capitalize(profile.gender) : null} />
            <Row label="Interested in" value={profile.orientation ? capitalize(profile.orientation) : null} />
            <Row label="Birth date" value={profile.birth_date ? formatDate(profile.birth_date) : null} />
            <Row label="City" value={profile.city} />
        </div>
    );
}
