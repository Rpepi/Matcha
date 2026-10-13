import { Link } from "react-router-dom";
import { useProfileContext } from "@/context/ProfileContext";
import LoadingScreen from "@/components/LoadingScreen";
import AppLayout from "@/components/AppLayout";

function NotFoundContent({ to, label }: { to: string; label: string }) {
    return (
        <div className="flex min-h-dvh flex-col items-center justify-center gap-2 p-6 text-center">
            <h1 className="font-display text-3xl font-medium text-ink">Page not found</h1>
            <Link to={to} className="mt-4 font-medium text-matcha hover:underline">
                {label}
            </Link>
        </div>
    );
}

export default function NotFoundPage() {
    const { status } = useProfileContext();

    if (status === "loading") return <LoadingScreen />;

    if (status === "complete") {
        return (
            <AppLayout>
                <NotFoundContent to="/browse" label="Back to Browse" />
            </AppLayout>
        );
    }

    if (status === "incomplete") {
        return <NotFoundContent to="/complete-profile" label="Back to your profile setup" />;
    }

    return <NotFoundContent to="/login" label="Back to Log in" />;
}
