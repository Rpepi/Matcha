import { useState, useEffect, type SubmitEvent } from "react";
import { login } from "../api/auth";
import { useNavigate, useSearchParams, Link } from "react-router-dom";
import AuthLayout from "../components/AuthLayout";
import { Field, GradientButton, FormNotice, OrDivider } from "../components/FormControls";
import GoogleAuthButton from "../components/GoogleAuthButton";
import ErrorPopup from "../components/ErrorPopup";

export default function LoginPage() {
    const [email, setEmail] = useState('');
    const [password, setPassword] = useState('');
    const [error, setError] = useState('')
    const [searchParams, setSearchParams] = useSearchParams();
    const [oauthErrorOpen, setOauthErrorOpen] = useState(false);
    const navigate = useNavigate()
    let loginPossible = false

    if ( password && email )
        loginPossible = true;
    else
        loginPossible = false;

    useEffect(() => {
        if (!searchParams.get('error'))
            return;
        setOauthErrorOpen(true);
        const next = new URLSearchParams(searchParams);
        next.delete('error');
        setSearchParams(next, { replace: true });
    }, [searchParams, setSearchParams]);

    const HandleSubmit = async (event: SubmitEvent<HTMLFormElement>) => {
        event.preventDefault()
        const response = await login(email, password)
        if (response.ok) {
            const data = await response.json();
            navigate(data.profile_complete ? '/browse' : '/complete-profile');
        }
        else
            setError('Invalid email or password')
    }

    return (
        <AuthLayout>
            <h2 className="font-display text-3xl font-medium text-plum">Log in</h2>
            <p className="mt-1.5 text-sm text-plum/60">
                Welcome back to your matches.
            </p>

            <div className="mt-8 flex flex-col gap-4">
                <GoogleAuthButton label="Log in with Google" />
                <OrDivider />
            </div>

            <form className="mt-4 flex flex-col gap-4" onSubmit={HandleSubmit} noValidate>
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
                <Field
                    label="Password"
                    id="password"
                    name="password"
                    type="password"
                    autoComplete="current-password"
                    value={password}
                    onChange={(e) => setPassword(e.target.value)}
                    required
                />

                <FormNotice tone="error">{error}</FormNotice>

                <GradientButton disabled={!loginPossible} type="submit" className="mt-2">
                    Log in
                </GradientButton>
            </form>

            <p className="mt-8 text-center text-sm text-plum/60">
                Not a member?{" "}
                <Link to="/register" className="font-medium text-orchid hover:underline">
                    Register now
                </Link>
            </p>

            <ErrorPopup
                open={oauthErrorOpen}
                onOpenChange={setOauthErrorOpen}
                message="We couldn't sign you in with Google. Please try again or use your email and password."
            />
        </AuthLayout>
    );
}
