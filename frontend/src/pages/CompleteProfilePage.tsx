import { useState, useEffect, type SubmitEvent } from "react";
import { useNavigate } from "react-router-dom";
import AuthLayout from "../components/AuthLayout";
import { Field, SelectField, GradientButton, FormNotice } from "../components/FormControls";
import { updateProfile, updateLocation } from "../api/profile";
import registerAvatar from "../assets/register_avatar.jpg"

export default function CompleteProfilePage() {
    const [email, setEmail] = useState('');
    const [gender, setGender] = useState('');
    const [orientation, setOrientation] = useState('');
    const [bio, setBio] = useState('');
    const [birth_date, setBirthDate] = useState('');
    const [latitude, setLatitude] = useState<number | ''>('');
    const [longitude, setLongitude] = useState<number | ''>('');
    const [city, setCity] = useState('');

    const [error, setError] = useState('');
    const [isLoading, setIsLoading] = useState(false);
    const navigate = useNavigate();

    useEffect(() => {
        fetch('/api/profile/me', { credentials: 'include' })
            .then(async (res) => {
                if (!res.ok) {
                    navigate('/login');
                    return;
                }
                const data = await res.json();
                if (data.profile_complete) {
                    navigate('/browse');
                    return;
                }
                setEmail(data.email ?? '');
            })
            .catch(() => setError('Could not load your account. Please try again.'));
    }, [navigate]);

    const HandleSubmit = async (event: SubmitEvent<HTMLFormElement>) => {
        event.preventDefault();
        if (isLoading)
            return;
        setError('');
        setIsLoading(true);

        const response = await updateProfile({ gender, orientation, bio, birth_date, city: city || null });

        if (!response.ok) {
            setError('Could not save your profile. Please check your details and try again.');
            setIsLoading(false);
            return;
        }

        if (latitude !== '' && longitude !== '') {
            const locationResponse = await updateLocation(Number(latitude), Number(longitude));
            if (!locationResponse.ok) {
                setError('Profile saved, but we could not save your location. You can add it later.');
                setIsLoading(false);
                return;
            }
        }

        navigate('/browse');
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
            eyebrow="Matcha · Almost there"
            headline="Finish your profile."
            tagline="You're signed in with Google. A few more details and you're ready to match."
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
                Complete your profile
            </h2>
            <p className="mt-1.5 text-sm text-plum/60">
                {email ? `Signed in as ${email}.` : 'Just a couple more details.'}
            </p>

            <form className="mt-8 flex flex-col gap-4" onSubmit={HandleSubmit} noValidate>
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
                    {latitude !== '' && longitude !== '' && (
                        <p className="mt-1.5 text-xs text-plum/50">
                            Location detected ({Number(latitude).toFixed(2)}, {Number(longitude).toFixed(2)})
                        </p>
                    )}
                </div>

                <FormNotice tone="error">{error}</FormNotice>

                <GradientButton type="submit" disabled={isLoading} className="mt-2">
                    {isLoading ? 'Saving…' : 'Finish setting up'}
                </GradientButton>
            </form>
        </AuthLayout>
    );
}
