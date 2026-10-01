export function popularityScore(fameRating: number): string {
    return Math.min(10, Math.max(0, fameRating)).toFixed(1);
}
