import { useState, useEffect, type SubmitEvent } from "react";
import { register } from "../api/auth";
import { useNavigate, useSearchParams, Link } from "react-router-dom";
import AuthLayout from "../components/AuthLayout";
import {
    Field,
    GradientButton,
    FormNotice,
    OrDivider,
} from "../components/FormControls";
import GoogleAuthButton from "../components/GoogleAuthButton";
import ErrorPopup from "../components/ErrorPopup";

export default function RegisterPage() {
    const [password, setPassword] = useState('');
    const [email, setEmail] = useState('');
    const [first_name, setFirstName] = useState('');
    const [last_name, setLastName] = useState('');

    const [error, setError] = useState('');
    const [info, setInfo] = useState('');
    const [isLoading, setIsLoading] = useState(false);
    const [oauthErrorOpen, setOauthErrorOpen] = useState(false);
    const [searchParams, setSearchParams] = useSearchParams();
    const navigate = useNavigate();

    useEffect(() => {
        if (!searchParams.get('error'))
            return;
        setOauthErrorOpen(true);
        const next = new URLSearchParams(searchParams);
        next.delete('error');
        setSearchParams(next, { replace: true });
    }, [searchParams, setSearchParams]);

    const HandleSubmit = async (event: SubmitEvent<HTMLFormElement>) => {
        event.preventDefault();
        if (isLoading)
            return;
        setError('');
        setInfo('');
        setIsLoading(true)
        const response = await register(password, email, first_name, last_name);

        if (response.ok)
        {
            setInfo('Account Created Succesfully, Check your email to verify your account.');
            setTimeout(() => navigate('/login'), 3000);
            return ;
        }
        else
        {
            try {
                const data = await response.json();
                setError(data.detail || 'Invalid or missing field.');
            }
            catch {
                setError(`Server error (${response.status}). Please try again`);
            }
        }
        setIsLoading(false);
    }

    return (
        <AuthLayout>
            <h2 className="font-display text-3xl font-medium text-plum">
                Create your account
            </h2>
            <p className="mt-1.5 text-sm text-plum/60">
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

                <FormNotice tone="info">{info}</FormNotice>
                <FormNotice tone="error">{error}</FormNotice>

                <GradientButton type="submit" disabled={isLoading} className="mt-2">
                    {isLoading ? 'Creating account…' : 'Create account'}
                </GradientButton>
            </form>

            <p className="mt-8 text-center text-sm text-plum/60">
                Already on Matcha?{" "}
                <Link to="/login" className="font-medium text-orchid hover:underline">
                    Log in
                </Link>
            </p>

            <ErrorPopup
                open={oauthErrorOpen}
                onOpenChange={setOauthErrorOpen}
                message="We couldn't sign you up with Google. Please try again or register with your email and password."
            />
        </AuthLayout>
    );
}
