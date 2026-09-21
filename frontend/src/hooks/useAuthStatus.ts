import { useProfileContext, type AuthStatus } from "../context/ProfileContext";

export type { AuthStatus };

export function useAuthStatus(): AuthStatus {
    return useProfileContext().status;
}
