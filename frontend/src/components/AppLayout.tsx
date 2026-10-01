import type { ReactNode } from "react";
import Sidebar from "./Sidebar";

export default function AppLayout({ children }: { children: ReactNode }) {
    return (
        <div className="min-h-screen bg-paper">
            <Sidebar />
            <main className="pb-20 md:pb-0 md:pl-18">{children}</main>
        </div>
    );
}
