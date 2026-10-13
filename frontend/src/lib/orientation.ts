// The API stores an orientation (hetero, homo, bi) relative to the user's own gender.
// People answer "who would you like to meet?" more easily than they pick a label,
// so the forms show who each orientation means for the chosen gender.

export const ORIENTATIONS = ["hetero", "homo", "bi"] as const;

/** Who an orientation means for someone of this gender: mirrors is_interested() in backend/app/matching.py. */
export function interestedInLabel(orientation: string, gender: string | null): string {
    if (orientation === "bi") return "Everyone";
    if (gender === "male") return orientation === "hetero" ? "Women" : "Men";
    if (gender === "female") return orientation === "hetero" ? "Men" : "Women";
    // Gender "other": hetero means men and women, homo means others who chose "other".
    return orientation === "hetero" ? "Men and women" : "People who chose \"Other\"";
}

export function interestedInOptions(gender: string | null): { value: string; label: string }[] {
    return ORIENTATIONS.map((value) => ({ value, label: interestedInLabel(value, gender) }));
}

/** The label shown on a public profile. No orientation counts as bisexual (the subject's rule). */
export function orientationLabel(orientation: string | null, gender: string | null): string {
    if (orientation === "hetero") return "Straight";
    if (orientation === "homo") return gender === "female" ? "Lesbian" : "Gay";
    return "Bisexual";
}
