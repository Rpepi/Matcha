import { useState, type SubmitEvent } from "react";
import { login } from "../api/auth";
import { useNavigate, Link } from "react-router-dom";
import AuthLayout from "../components/AuthLayout";
import { Field, GradientButton, FormNotice } from "../components/FormControls";
import LoginAvatar from "../assets/login_avatar.jpg"

export default function LoginPage() {
    const [email, setEmail] = useState('');
    const [password, setPassword] = useState('');
    const [error, setError] = useState('')
    const navigate = useNavigate()
    let loginPossible = false

    if ( password && email )
        loginPossible = true;
    else
        loginPossible = false;


    const HandleSubmit = async (event: SubmitEvent<HTMLFormElement>) => {
        event.preventDefault()
        const response = await login(email, password)
        if (response.ok)
            navigate('/browse')
        else
            setError('Invalid email or password')
    }

    return (
        <AuthLayout
            eyebrow="Matcha · Sign in"
            headline="Good, you're back."
            tagline="Someone out there is one match away from becoming a very long conversation."
            frontSlot={
                <div className="flex h-full flex-col justify-between p-6">
                    <span className="inline-flex w-fit items-center gap-1.5 rounded-full bg-white/10 px-3 py-1 text-xs font-medium text-petal/80">
                        <span className="h-1.5 w-1.5 rounded-full bg-bloom" />
                        Active nearby
                    </span>
                    <div className="my-4 ml-4 flex-1 min-h-0 overflow-hidden rounded-lg">
                        <img className="rounded-lg object-center" src={LoginAvatar} />
                    </div>
                    <p className="font-display text-xl italic text-petal/90">
                        
                    </p>
                </div>
            }
        >
            <h2 className="font-display text-3xl font-medium text-plum">Log in</h2>
            <p className="mt-1.5 text-sm text-plum/60">
                Welcome back to your matches.
            </p>

            <form className="mt-8 flex flex-col gap-4" onSubmit={HandleSubmit} noValidate>
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
        </AuthLayout>
    );
}
