function GoogleIcon() {
    return (
        <svg viewBox="0 0 18 18" className="h-4.5 w-4.5" aria-hidden="true">
            <path
                fill="#4285F4"
                d="M17.64 9.204c0-.638-.057-1.252-.164-1.841H9v3.481h4.844a4.14 4.14 0 0 1-1.796 2.717v2.258h2.908c1.702-1.567 2.684-3.875 2.684-6.615Z"
            />
            <path
                fill="#34A853"
                d="M9 18c2.43 0 4.467-.806 5.956-2.181l-2.908-2.259c-.806.54-1.837.86-3.048.86-2.344 0-4.328-1.584-5.036-3.711H.957v2.332A8.997 8.997 0 0 0 9 18Z"
            />
            <path
                fill="#FBBC05"
                d="M3.964 10.71A5.4 5.4 0 0 1 3.68 9c0-.593.102-1.17.284-1.71V4.958H.957A8.996 8.996 0 0 0 0 9c0 1.452.348 2.827.957 4.042l3.007-2.332Z"
            />
            <path
                fill="#EA4335"
                d="M9 3.58c1.321 0 2.508.454 3.44 1.345l2.581-2.58C13.463.891 11.426 0 9 0A8.997 8.997 0 0 0 .957 4.958l3.007 2.332C4.672 5.163 6.656 3.58 9 3.58Z"
            />
        </svg>
    );
}

interface GoogleAuthButtonProps {
    label?: string;
}

export default function GoogleAuthButton({ label = "Continue with Google" }: GoogleAuthButtonProps) {
    return (
        <a
            href="/api/oauth/google/login"
            className="flex w-full items-center justify-center gap-2.5 rounded-xl border border-ink/15 px-4 py-2.5 text-sm font-medium text-ink transition hover:bg-ink/5 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-orchid"
        >
            <GoogleIcon />
            {label}
        </a>
    );
}
