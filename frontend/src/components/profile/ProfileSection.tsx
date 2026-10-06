import type { ReactNode } from "react";

export default function ProfileSection({ children, className = "" }: { children: ReactNode; className?: string }) {
    return <div className={`rounded-3xl bg-grey/5 px-6 py-5 ${className}`}>{children}</div>;
}
