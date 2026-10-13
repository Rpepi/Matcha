// Chrome prints every 4xx answer to fetch() as a red "Failed to load resource"
// line in the console, even when the app expected it and handles it (a wrong
// password, a weak password, a refused like). So every call to our API asks the
// backend for "soft" errors: a 4xx then travels as a 200 with the real status in
// `X-Status` (see SoftErrorsMiddleware in backend/app/__init__.py), and this
// wrapper puts the real status back before any app code sees the response.
// `response.ok` and `response.status` therefore mean exactly what they always
// did; only the console stays quiet. Server errors (5xx) are never softened.

const SOFT_ERRORS_HEADER = "X-Soft-Errors";
const STATUS_HEADER = "X-Status";

function isOurApi(input: RequestInfo | URL): boolean {
    const raw = typeof input === "string" ? input : input instanceof URL ? input.href : input.url;
    const url = new URL(raw, window.location.href);
    return url.origin === window.location.origin && url.pathname.startsWith("/api/");
}

/** Wraps `window.fetch` once, at startup (see main.tsx). Other origins (OpenStreetMap) are untouched. */
export function installSoftErrors(): void {
    const nativeFetch = window.fetch.bind(window);

    window.fetch = async (input: RequestInfo | URL, init?: RequestInit): Promise<Response> => {
        if (!isOurApi(input)) return nativeFetch(input, init);

        const headers = new Headers(init?.headers ?? (input instanceof Request ? input.headers : undefined));
        headers.set(SOFT_ERRORS_HEADER, "1");
        const response = await nativeFetch(input, { ...init, headers });

        const realStatus = Number(response.headers.get(STATUS_HEADER));
        if (!Number.isInteger(realStatus) || realStatus < 400 || realStatus > 499) return response;
        return new Response(response.body, { status: realStatus, headers: response.headers });
    };
}
