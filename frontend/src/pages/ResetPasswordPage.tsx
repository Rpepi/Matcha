import { useState, type SubmitEvent } from "react";
import { Link, useNavigate, useSearchParams } from "react-router-dom";
import { resetPassword } from "@/api/auth";
import { useToast } from "@/context/ToastContext";
import AuthLayout from "@/components/AuthLayout";
import { Field, Button, FormNotice } from "@/components/FormControls";

export default function ResetPasswordPage() {
    const [searchParams] = useSearchParams();
    const token = searchParams.get("token");
    const [password, setPassword] = useState("");
    const [isLoading, setIsLoading] = useState(false);
    const navigate = useNavigate();
    const { showNotice } = useToast();
    const [formError, setFormError] = useState("");

    async function handleSubmit(event: SubmitEvent<HTMLFormElement>) {
        event.preventDefault();
        if (isLoading || !token) return;
        setIsLoading(true);
        setFormError("");

        try {
            const response = await resetPassword(token, password);
            const data = await response.json().catch(() => null);

            if (response.ok) {
                showNotice(data?.message ?? "Password updated. You can now log in.");
                setTimeout(() => navigate("/login"), 3000);
                return;
            }

            setFormError(data?.detail ?? "Could not reset your password. Please try again.");
        } catch {
            setFormError("Network error. Check your connection and try again.");
        } finally {
            setIsLoading(false);
        }
    }

    return (
        <AuthLayout>
            <h2 className="font-display text-3xl font-medium text-ink">Reset password</h2>
            <p className="mt-1.5 text-sm text-ink/60">Choose a new password for your account.</p>

            {!token ? (
                <div className="mt-6 flex flex-col gap-4">
                    <FormNotice>This reset link is invalid. Please request a new one.</FormNotice>
                    <Link to="/forgot-password" className="text-center text-sm font-medium text-matcha hover:underline">
                        Request a new link
                    </Link>
                </div>
            ) : (
                <form className="mt-6 flex flex-col gap-4" onSubmit={handleSubmit} noValidate>
                    <Field
                        label="New password"
                        id="password"
                        name="password"
                        type="password"
                        autoComplete="new-password"
                        value={password}
                        onChange={(e) => setPassword(e.target.value)}
                        required
                    />

                    <FormNotice>{formError}</FormNotice>

                    <Button disabled={!password || isLoading} type="submit" className="mt-2">
                        {isLoading ? "Resetting…" : "Reset password"}
                    </Button>
                </form>
            )}
        </AuthLayout>
    );
}
