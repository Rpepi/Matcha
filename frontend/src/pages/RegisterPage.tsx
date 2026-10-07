import { useState, useEffect, type SubmitEvent } from "react";
import { register } from "../api/auth";
import { useNavigate, useSearchParams, Link } from "react-router-dom";
import { useToast } from "../context/ToastContext";
import AuthLayout from "../components/AuthLayout";
import {
    Field,
    Button,
    OrDivider,
} from "../components/FormControls";
import GoogleAuthButton from "../components/GoogleAuthButton";

export default function RegisterPage() {
    const [password, setPassword] = useState('');
    const [email, setEmail] = useState('');
    const [username, setUsername] = useState('');
    const [first_name, setFirstName] = useState('');
    const [last_name, setLastName] = useState('');

    const [isLoading, setIsLoading] = useState(false);
    const [searchParams, setSearchParams] = useSearchParams();
    const navigate = useNavigate();
    const { showError, showNotice } = useToast();

    useEffect(() => {
        if (!searchParams.get('error'))
            return;
        showError("We couldn't sign you up with Google. Please try again or register with your email and password.");
        const next = new URLSearchParams(searchParams);
        next.delete('error');
        setSearchParams(next, { replace: true });
    }, [searchParams, setSearchParams, showError]);

    const HandleSubmit = async (event: SubmitEvent<HTMLFormElement>) => {
        event.preventDefault();
        if (isLoading)
            return;
        setIsLoading(true)
        const response = await register(password, email, username.trim(), first_name, last_name);

        if (response.ok)
        {
            showNotice('Account created successfully — check your email to verify your account.');
            setTimeout(() => navigate('/login'), 3000);
            return ;
        }
        else
        {
            try {
                const data = await response.json();
                showError(data.detail || 'Invalid or missing field.');
            }
            catch {
                showError(`Server error (${response.status}). Please try again`);
            }
        }
        setIsLoading(false);
    }

    return (
        <AuthLayout>
            <h2 className="font-display text-3xl font-medium text-ink">
                Create your account
            </h2>
            <p className="mt-1.5 text-sm text-ink/60">
                Just the basics for now.
            </p>

            <div className="mt-8 flex flex-col gap-4">
                <GoogleAuthButton label="Sign up with Google" />
                <OrDivider />
            </div>

            <form className="mt-4 flex flex-col gap-4" onSubmit={HandleSubmit} noValidate>
                <div className="grid grid-cols-2 gap-4">
                    <Field
                        label="First name"
                        id="first_name"
                        type="text"
                        autoComplete="given-name"
                        value={first_name}
                        onChange={(e) => setFirstName(e.target.value)}
                        required
                    />
                    <Field
                        label="Last name"
                        id="last_name"
                        type="text"
                        autoComplete="family-name"
                        value={last_name}
                        onChange={(e) => setLastName(e.target.value)}
                        required
                    />
                </div>

                <Field
                    label="Username"
                    id="username"
                    type="text"
                    autoComplete="username"
                    minLength={3}
                    maxLength={30}
                    value={username}
                    onChange={(e) => setUsername(e.target.value)}
                    required
                />
                <Field
                    label="Email"
                    id="email"
                    type="email"
                    autoComplete="email"
                    value={email}
                    onChange={(e) => setEmail(e.target.value)}
                    required
                />
                <Field
                    label="Password"
                    id="password"
                    type="password"
                    autoComplete="new-password"
                    value={password}
                    onChange={(e) => setPassword(e.target.value)}
                    required
                />

                <Button type="submit" disabled={isLoading} className="mt-2">
                    {isLoading ? 'Creating account…' : 'Create account'}
                </Button>
            </form>

            <p className="mt-8 text-center text-sm text-ink/60">
                Already on Matcha?{" "}
                <Link to="/login" className="font-medium text-matcha hover:underline">
                    Log in
                </Link>
            </p>
        </AuthLayout>
    );
}
