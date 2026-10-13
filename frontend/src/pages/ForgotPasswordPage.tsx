import { useState, type SubmitEvent } from "react";
import { Link } from "react-router-dom";
import { forgotPassword } from "@/api/auth";
import { useToast } from "@/context/ToastContext";
import AuthLayout from "@/components/AuthLayout";
import { Field, Button, FormNotice } from "@/components/FormControls";

const GENERIC_MESSAGE = "A reset link has been sent.";

export default function ForgotPasswordPage() {
    const [email, setEmail] = useState("");
    const [isLoading, setIsLoading] = useState(false);
    const [sent, setSent] = useState(false);
    const { showError } = useToast();

    async function handleSubmit(event: SubmitEvent<HTMLFormElement>) {
        event.preventDefault();
        if (isLoading) return;
        setIsLoading(true);

        try {
            const response = await forgotPassword(email);
            if (response.status === 429) {
                showError("You're doing that too fast. Please wait a moment and try again.");
            } else if (response.ok) {
                setSent(true);
            } else {
                const data = await response.json().catch(() => null);
                showError(data?.detail ?? "Could not send the reset email. Please try again.");
            }
        } catch {
            showError("Network error. Check your connection and try again.");
        } finally {
            setIsLoading(false);
        }
    }

    return (
        <AuthLayout>
            <h2 className="font-display text-3xl font-medium text-ink">Forgot password?</h2>
            <p className="mt-1.5 text-sm text-ink/60">
                Enter your email and we'll send you a link to reset it.
            </p>

            {sent ? (
                <div className="mt-6 flex flex-col gap-4">
                    <FormNotice tone="info">{GENERIC_MESSAGE}</FormNotice>
                    <Link to="/login" className="text-center text-sm font-medium text-matcha hover:underline">
                        Back to log in
                    </Link>
                </div>
            ) : (
                <>
                    <form className="mt-6 flex flex-col gap-4" onSubmit={handleSubmit} noValidate>
                        <Field
                            label="Email"
                            id="email"
                            name="email"
                            type="email"
                            autoComplete="email"
                            value={email}
                            onChange={(e) => setEmail(e.target.value)}
                            required
                        />

                        <Button disabled={!email || isLoading} type="submit" className="mt-2">
                            {isLoading ? "Sending…" : "Send reset link"}
                        </Button>
                    </form>

                    <p className="mt-8 text-center text-sm text-ink/60">
                        Remembered it?{" "}
                        <Link to="/login" className="font-medium text-matcha hover:underline">
                            Log in
                        </Link>
                    </p>
                </>
            )}
        </AuthLayout>
    );
}
