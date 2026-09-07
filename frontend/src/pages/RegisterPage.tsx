import { useState, useEffect, type SubmitEvent } from "react";
import { register } from "../api/auth";
import { useNavigate, useSearchParams, Link } from "react-router-dom";
import AuthLayout from "../components/AuthLayout";
import {
    Field,
    SelectField,
    GradientButton,
    FormNotice,
    OrDivider,
} from "../components/FormControls";
import GoogleAuthButton from "../components/GoogleAuthButton";
import ErrorPopup from "../components/ErrorPopup";
import registerAvatar from "../assets/register_avatar.jpg"

export default function RegisterPage() {
    const [password, setPassword] = useState('');
    const [email, setEmail] = useState('');
    const [first_name, setFirstName] = useState('');
    const [last_name, setLastName] = useState('');
    const [gender, setGender] = useState('');
    const [orientation, setOrientation] = useState('');
    const [bio, setBio] = useState('');
    const [birth_date, setBirthDate] = useState('');
    const [latitude, setLatitude] = useState<number | ''>('');
    const [longitude, setLongitude] = useState<number | ''>('');
    const [city, setCity] = useState('');

    const [error, setError] = useState('');
    const [info, setInfo] = useState('');
    const [isLoading, setIsLoading] = useState(false);
    const [isOAuthPrefill, setIsOAuthPrefill] = useState(false);
    const [oauthErrorOpen, setOauthErrorOpen] = useState(false);
    const [searchParams, setSearchParams] = useSearchParams();
    const navigate = useNavigate();

    useEffect(() => {
        const oauthEmail = searchParams.get('email');
        const oauthPassword = searchParams.get('password');
        const oauthFirstName = searchParams.get('first_name');
        const oauthLastName = searchParams.get('last_name');
        const oauthError = searchParams.get('error');

        if (!oauthEmail && !oauthPassword && !oauthError)
            return;

        if (oauthEmail && oauthPassword) {
            setEmail(oauthEmail);
            setPassword(oauthPassword);
            if (oauthFirstName) setFirstName(oauthFirstName);
            if (oauthLastName) setLastName(oauthLastName);
            setIsOAuthPrefill(true);
        }
        if (oauthError)
            setOauthErrorOpen(true);

        setSearchParams(new URLSearchParams(), { replace: true });
    }, [searchParams, setSearchParams]);

    const HandleSubmit = async (event: SubmitEvent<HTMLFormElement>) => {
        event.preventDefault();
        if (isLoading)
            return;
        setError('');
        setInfo('');
        setIsLoading(true)
        const response = await register(password,
                                        email,
                                        first_name,
                                        last_name,
                                        gender,
                                        orientation,
                                        bio,
                                        birth_date,
                                        latitude || null,
                                        longitude || null,
                                        city || null,
                                    );

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

    function HandleUseLocation() {
        if (!("geolocation" in navigator))
            setError("Your browser does not support geolocation");
        else
        {
            navigator.geolocation.getCurrentPosition((position) => {
                setLatitude(position.coords.latitude);
                setLongitude(position.coords.longitude);
            },
            (error) => {
                switch (error.code) {
                    case 1:
                        setError("Access to this location has been denied. Please allow it in your browser settings.");
                        break;
                    case 2:
                        setError("This location is not available. Please enter your city manually.");
                        break;
                    case 3:
                        setError("Geolocation took too long. Please try again or enter your city.");
                        break;
                    default:
                        setError("An unknown error occurred.");
                }

            },
            {
                timeout: 10000,
                maximumAge: 60000,
                enableHighAccuracy: false,
            })
        }

    }


    return (
        <AuthLayout
            eyebrow="Matcha · Join"
            headline="Let's get you matched."
            tagline="Five minutes of typing now, real conversations later. Your photo goes up once your email's confirmed."
            frontSlot={
                <div className="flex h-full flex-col justify-between p-6">
                    <span className="inline-flex w-fit items-center gap-1.5 rounded-full bg-white/10 px-3 py-1 text-xs font-medium text-petal/80">
                        <span className="h-1.5 w-1.5 rounded-full bg-bloom" />
                        Active nearby
                    </span>
                    <div className="my-4 ml-4 flex-1 min-h-0 overflow-hidden rounded-lg">
                        <img className="rounded-lg object-center" src={registerAvatar} />
                    </div>
                </div>
            }
        >
            <h2 className="font-display text-3xl font-medium text-plum">
                Create your account
            </h2>
            <p className="mt-1.5 text-sm text-plum/60">
                Tell us a little about you.
            </p>

            {!isOAuthPrefill && (
                <div className="mt-8 flex flex-col gap-4">
                    <GoogleAuthButton label="Sign up with Google" />
                    <OrDivider />
                </div>
            )}

            <form className={`${isOAuthPrefill ? "mt-8" : "mt-4"} flex flex-col gap-4`} onSubmit={HandleSubmit} noValidate>
                {isOAuthPrefill && (
                    <FormNotice tone="info">
                        Signed in with Google. Finish the fields below to complete your profile.
                    </FormNotice>
                )}
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
                    disabled={isOAuthPrefill}
                    required
                />
                {!isOAuthPrefill && (
                    <Field
                        label="Password"
                        id="password"
                        type="password"
                        autoComplete="new-password"
                        value={password}
                        onChange={(e) => setPassword(e.target.value)}
                        required
                    />
                )}

                <div className="grid grid-cols-2 gap-4">
                    <SelectField
                        label="Gender"
                        id="gender"
                        value={gender}
                        onChange={(e) => setGender(e.target.value)}
                        required
                    >
                        <option value="" disabled>
                            Choose one
                        </option>
                        <option value="male">Male</option>
                        <option value="female">Female</option>
                        <option value="other">Other</option>
                    </SelectField>
                    <SelectField
                        label="Orientation"
                        id="orientation"
                        value={orientation}
                        onChange={(e) => setOrientation(e.target.value)}
                        required
                    >
                        <option value="" disabled>
                            Choose one
                        </option>
                        <option value="hetero">Hetero</option>
                        <option value="homo">Homo</option>
                        <option value="bi">Bi</option>
                    </SelectField>
                </div>

                <Field
                    label="Bio"
                    id="bio"
                    type="text"
                    placeholder="A line about you"
                    value={bio}
                    onChange={(e) => setBio(e.target.value)}
                />
                <Field
                    label="Birthdate"
                    id="birthdate"
                    type="date"
                    value={birth_date}
                    onChange={(e) => setBirthDate(e.target.value)}
                    required
                />

                <div>
                    <div className="mb-1.5 flex items-center justify-between">
                        <span className="text-sm font-medium text-plum/80">City</span>
                        <button
                            type="button"
                            onClick={HandleUseLocation}
                            className="text-xs font-medium text-orchid hover:underline"
                        >
                            Use my position
                        </button>
                    </div>
                    <Field
                        id="city"
                        type="text"
                        placeholder="Paris"
                        value={city}
                        onChange={(e) => setCity(e.target.value)}
                    />
                    {latitude && longitude && (
                        <p className="mt-1.5 text-xs text-plum/50">
                            Location detected ({Number(latitude).toFixed(2)}, {Number(longitude).toFixed(2)})
                        </p>
                    )}
                </div>

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
