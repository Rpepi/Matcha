const HAS_ZONE = /(Z|[+-]\d{2}:?\d{2})$/;
const DAY_MS = 86_400_000;

const TIME = new Intl.DateTimeFormat(undefined, { hour: "2-digit", minute: "2-digit" });
const WEEKDAY_LONG = new Intl.DateTimeFormat(undefined, { weekday: "long" });
const WEEKDAY_SHORT = new Intl.DateTimeFormat(undefined, { weekday: "short" });
const DATE_LONG = new Intl.DateTimeFormat(undefined, { day: "numeric", month: "long", year: "numeric" });
const DATE_SHORT = new Intl.DateTimeFormat(undefined, { day: "numeric", month: "short" });

/**
 * The backend stores `TIMESTAMP` (no zone) from a UTC database and serializes
 * them without a zone (`2026-10-03T10:12:00`). `new Date()` would read that as
 * local time, so a missing zone is taken as UTC.
 */
export function parseServerDate(value: string): Date {
    return new Date(HAS_ZONE.test(value) ? value : `${value}Z`);
}

function startOfDay(date: Date): number {
    return new Date(date.getFullYear(), date.getMonth(), date.getDate()).getTime();
}

/** Calendar days between `date` and `now` in local time (0 = today). Rounded for DST days. */
function calendarDaysAgo(date: Date, now: Date): number {
    return Math.round((startOfDay(now) - startOfDay(date)) / DAY_MS);
}

export function dayKey(value: string): string {
    const date = parseServerDate(value);
    return `${date.getFullYear()}-${date.getMonth()}-${date.getDate()}`;
}

export function formatMessageTime(value: string): string {
    return TIME.format(parseServerDate(value));
}

/** Separator label between days inside a conversation. */
export function formatDayLabel(value: string, now: Date = new Date()): string {
    const date = parseServerDate(value);
    const days = calendarDaysAgo(date, now);
    if (days <= 0) return "Today";
    if (days === 1) return "Yesterday";
    if (days < 7) return WEEKDAY_LONG.format(date);
    return DATE_LONG.format(date);
}

/** Compact timestamp for the conversation list. */
export function formatListTime(value: string, now: Date = new Date()): string {
    const date = parseServerDate(value);
    const days = calendarDaysAgo(date, now);
    if (days <= 0) return TIME.format(date);
    if (days === 1) return "Yesterday";
    if (days < 7) return WEEKDAY_SHORT.format(date);
    if (date.getFullYear() === now.getFullYear()) return DATE_SHORT.format(date);
    return DATE_LONG.format(date);
}

/**
 * Last connection with its date and its time, for a profile: "Last seen today at 14:32",
 * "Last seen yesterday at 09:10", "Last seen Monday at 18:05", "Last seen October 3, 2026 at 18:05".
 * `null` (never seen: an account from before presence was recorded) reads as plain "Offline".
 */
export function formatLastSeenAt(value: string | null, now: Date = new Date()): string {
    if (!value) return "Offline";
    const day = formatDayLabel(value, now);
    return `Last seen ${day === "Today" || day === "Yesterday" ? day.toLowerCase() : day} at ${formatMessageTime(value)}`;
}

export function formatLastSeen(value: string | null, now: Date = new Date()): string {
    if (!value) return "Offline";
    const date = parseServerDate(value);
    const minutes = Math.max(0, Math.floor((now.getTime() - date.getTime()) / 60_000));
    if (minutes < 1) return "Last seen just now";
    if (minutes < 60) return `Last seen ${minutes} min ago`;
    const hours = Math.floor(minutes / 60);
    if (hours < 24 && calendarDaysAgo(date, now) <= 0) return `Last seen ${hours} h ago`;
    const days = calendarDaysAgo(date, now);
    if (days <= 1) return "Last seen yesterday";
    if (days < 7) return `Last seen ${WEEKDAY_LONG.format(date)}`;
    return `Last seen ${DATE_SHORT.format(date)}`;
}
