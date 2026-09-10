import { useState, useEffect } from "react";
import { useNavigate } from "react-router-dom";
import { updateProfile, updateLocation } from "../api/profile";

export const STEP_COUNT = 5;

export function useOnboarding() {
    const [step, setStep] = useState(0);
    const [firstName, setFirstName] = useState('');

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
                setFirstName(data.first_name ?? '');
            })
            .catch(() => setError('Could not load your account. Please try again.'));
    }, [navigate]);

    function goNext() {
        setError('');
        setStep((s) => Math.min(s + 1, STEP_COUNT - 1));
    }

    function goBack() {
        setError('');
        setStep((s) => Math.max(s - 1, 0));
    }

    function HandleUseLocation() {
        if (!("geolocation" in navigator)) {
            setError("Your browser does not support geolocation");
            return;
        }
        navigator.geolocation.getCurrentPosition((position) => {
            setLatitude(position.coords.latitude);
            setLongitude(position.coords.longitude);
        },
        (geoError) => {
            switch (geoError.code) {
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

    function isAtLeast16(dateStr: string): boolean {
        const dob = new Date(dateStr);
        const today = new Date();
        let age = today.getFullYear() - dob.getFullYear();
        const hasHadBirthdayThisYear =
            today.getMonth() > dob.getMonth() ||
            (today.getMonth() === dob.getMonth() && today.getDate() >= dob.getDate());
        if (!hasHadBirthdayThisYear)
            age -= 1;
        return age >= 16;
    }

    function handleBirthdateNext() {
        if (!isAtLeast16(birth_date)) {
            setError("You must be at least 16 years old to use Matcha.");
            return;
        }
        goNext();
    }

    async function handleFinish() {
        if (!city && (latitude === '' || longitude === '')) {
            setError("Add your city or share your location so we can find matches near you.");
            return;
        }
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

    return {
        step,
        firstName,
        gender,
        setGender,
        orientation,
        setOrientation,
        bio,
        setBio,
        birth_date,
        setBirthDate,
        latitude,
        longitude,
        city,
        setCity,
        error,
        isLoading,
        goNext,
        goBack,
        HandleUseLocation,
        handleBirthdateNext,
        handleFinish,
    };
}
