// Identical GET requests still in flight share one network request.
//
// A page load asks for the same data from several places at once: the chat
// context and the chat page both load the conversations, and in development
// React runs every effect twice. Each of those requests used to reach the
// server, which counts them against its rate limits (10 back to back for the
// conversations): a few quick reloads were enough to be refused with a 429.
// Now they wait for the one request already on its way and each gets its own
// copy of the answer.

const pending = new Map<string, Promise<Response>>();

export function sharedGet(url: string): Promise<Response> {
    let request = pending.get(url);
    if (!request) {
        request = fetch(url, { credentials: "include" }).finally(() => pending.delete(url));
        pending.set(url, request);
    }
    // A body can be read only once: every caller reads its own clone.
    return request.then((response) => response.clone());
}
