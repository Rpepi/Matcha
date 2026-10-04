import type { ReactElement } from "react";
import { Link, NavLink } from "react-router-dom";
import { Tooltip } from "@base-ui/react/tooltip";
import { Search, Send, UserRound, LogOut, type LucideIcon } from "lucide-react";
import logo from "../assets/logo.png";
import { logout } from "../api/auth";
import { useProfileContext } from "../context/ProfileContext";
import { useChatContext } from "../context/ChatContext";

const NAV_ITEMS: { to: string; icon: LucideIcon; label: string }[] = [
    { to: "/browse", icon: Search, label: "Browse" },
    { to: "/chat", icon: Send, label: "Messages" },
    { to: "/profile", icon: UserRound, label: "Profile" },
];

function IconTooltip({ label, children }: { label: string; children: ReactElement }) {
    return (
        <Tooltip.Root>
            <Tooltip.Trigger delay={100} render={children} />
            <Tooltip.Portal>
                <Tooltip.Positioner side="right" sideOffset={10}>
                    <Tooltip.Popup className="rounded-md bg-ink px-2.5 py-1.5 text-xs font-medium text-paper shadow-md">
                        {label}
                    </Tooltip.Popup>
                </Tooltip.Positioner>
            </Tooltip.Portal>
        </Tooltip.Root>
    );
}

export default function Sidebar() {
    const { refetch } = useProfileContext();
    const { unreadTotal } = useChatContext();

    async function handleLogout() {
        await logout();
        await refetch();
    }

    return (
        <aside className="fixed left-0 right-0 bottom-0 z-30 flex items-center justify-around border-t-3 border-grey/15 bg-paper py-3 md:top-0 md:bottom-0 md:left-0 md:right-auto md:grid md:w-18 md:grid-rows-[auto_1fr_auto] md:items-center md:justify-items-center md:border-t-0 md:border-3 md:py-6">
            <Link to="/browse" aria-label="Matcha" className="hidden md:block">
                <img src={logo} alt="" className="h-9 w-9" />
            </Link>

            <nav className="flex items-center gap-6 md:flex-col md:gap-1">
                {NAV_ITEMS.map(({ to, icon: Icon, label }) => {
                    const badge = to === "/chat" ? unreadTotal : 0;
                    const description = badge > 0 ? `${label}, ${badge} unread` : label;

                    return (
                        <IconTooltip key={to} label={description}>
                            <NavLink
                                to={to}
                                aria-label={description}
                                className={({ isActive }) =>
                                    `relative cursor-pointer rounded-xl p-3 hover:bg-matcha/25 transition ${
                                        isActive ? "text-ink" : "text-grey hover:text-ink "
                                    }`
                                }
                            >
                                <Icon className="h-7 w-7" />
                                {badge > 0 && (
                                    <span
                                        aria-hidden="true"
                                        className="absolute top-1 right-1 flex h-5 min-w-5 items-center justify-center rounded-full bg-pink px-1 text-[11px] leading-none font-bold text-ink ring-2 ring-paper"
                                    >
                                        {badge > 99 ? "99+" : badge}
                                    </span>
                                )}
                            </NavLink>
                        </IconTooltip>
                    );
                })}
            </nav>

            <div className="hidden md:block">
                <IconTooltip label="Log out">
                    <button
                        type="button"
                        onClick={handleLogout}
                        aria-label="Log out"
                        className="cursor-pointer rounded-xl p-2 hover:bg-matcha/25 text-grey transition hover:text-ink"
                    >
                        <LogOut className="h-7 w-7" />
                    </button>
                </IconTooltip>
            </div>
        </aside>
    );
}
