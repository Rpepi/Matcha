import { Loader2 } from "lucide-react";

export default function LoadingScreen() {
    return (
        <div className="flex min-h-screen items-center justify-center bg-paper">
            <Loader2 className="h-6 w-6 animate-spin text-matcha" />
        </div>
    );
}
