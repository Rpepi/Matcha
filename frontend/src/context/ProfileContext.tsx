import { createContext, useContext, useState, useEffect, useCallback, type ReactNode } from "react";

export type AuthStatus = 'loading' | 'guest' | 'incomplete' | 'complete';

export interface Profile {
    id: number;
    email: string;
    /** A new address waiting for its confirmation link; `email` stays the active one until then. */
    pending_email: string | null;
    /** `google` accounts cannot change their email (Google finds the account by it). */
    auth_provider: "email" | "google";
    username: string;
    first_name: string;
    last_name: string;
    gender: string | null;
    orientation: string | null;
    bio: string | null;
    birth_date: string | null;
    fame_rating: number;
    latitude: number | null;
    longitude: number | null;
    city: string | null;
    is_online: boolean;
    last_seen: string | null;
    profile_complete: boolean;
    created_at: string;
    tags: string[];
    photos: { path: string; is_profile: boolean; position: number }[];
}

interface ProfileContextValue {
    status: AuthStatus;
    profile: Profile | null;
    refetch: () => Promise<void>;
}

const ProfileContext = createContext<ProfileContextValue | undefined>(undefined);

export function ProfileProvider({ children }: { children: ReactNode }) {
    const [status, setStatus] = useState<AuthStatus>('loading');
    const [profile, setProfile] = useState<Profile | null>(null);

    const refetch = useCallback(async () => {
        try {
            // A visitor is a normal case, not an error: /profile/me would answer them with a 401,
            // which the browser prints in red in the console on every page. This one answers 200.
            const sessionRes = await fetch('/api/auth/session', { credentials: 'include' });
            const session = sessionRes.ok ? await sessionRes.json() : null;
            if (!session?.authenticated) {
                setProfile(null);
                setStatus('guest');
                return;
            }

            const res = await fetch('/api/profile/me', { credentials: 'include' });
            if (!res.ok) {
                setProfile(null);
                setStatus('guest');
                return;
            }
            const data = await res.json();
            setProfile(data);
            setStatus(data.profile_complete ? 'complete' : 'incomplete');
        } catch {
            setProfile(null);
            setStatus('guest');
        }
    }, []);

    useEffect(() => {
        refetch();
    }, [refetch]);

    return (
        <ProfileContext.Provider value={{ status, profile, refetch }}>
            {children}
        </ProfileContext.Provider>
    );
}

export function useProfileContext(): ProfileContextValue {
    const ctx = useContext(ProfileContext);
    if (!ctx) throw new Error("useProfileContext must be used within a ProfileProvider");
    return ctx;
}
