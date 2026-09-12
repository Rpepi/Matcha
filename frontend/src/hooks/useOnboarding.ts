import { useState, useEffect } from "react";
import { useNavigate } from "react-router-dom";
import { updateProfile, updateLocation } from "../api/profile";
import { uploadPhoto as uploadPhotoApi, deletePhoto as deletePhotoApi, movePhoto as movePhotoApi } from "../api/photos";

export const STEP_COUNT = 6;

export interface OnboardingPhoto {
    position: number;
    url: string;
}

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
    const [photos, setPhotos] = useState<OnboardingPhoto[]>([]);
    const [isUploadingPhoto, setIsUploadingPhoto] = useState(false);

    const [error, setError] = useState('');
    const [isLoading, setIsLoading] = useState(false);
    const navigate = useNavigate();

    useEffect(() => {
        fetch('/api/profile/me', { credentials: 'include' })
            .then(async (res) => {
                if (!res.ok) return;
                const data = await res.json();
                setFirstName(data.first_name ?? '');
            })
            .catch(() => setError('Could not load your account. Please try again.'));
    }, []);

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

    async function uploadPhoto(file: File) {
        setError('');
        setIsUploadingPhoto(true);

        const usedPositions = photos.map((p) => p.position);
        const nextPosition = [1, 2, 3, 4, 5].find((p) => !usedPositions.includes(p));

        const response = await uploadPhotoApi(file);
        if (!response.ok) {
            const data = await response.json().catch(() => null);
            setError(data?.detail ?? 'Could not upload photo. Please try again.');
            setIsUploadingPhoto(false);
            return;
        }

        if (nextPosition !== undefined) {
            setPhotos((prev) => [...prev, { position: nextPosition, url: URL.createObjectURL(file) }]);
        }
        setIsUploadingPhoto(false);
    }

    async function deletePhoto(position: number) {
        setError('');
        const response = await deletePhotoApi(position);
        if (!response.ok) {
            const data = await response.json().catch(() => null);
            setError(data?.detail ?? 'Could not delete photo. Please try again.');
            return;
        }

        const remaining = photos
            .filter((p) => p.position !== position)
            .sort((a, b) => a.position - b.position);

        const compacted: OnboardingPhoto[] = [];
        for (const photo of remaining) {
            if (photo.position <= position) {
                compacted.push(photo);
                continue;
            }
            const newPosition = photo.position - 1;
            const moveResponse = await movePhotoApi(photo.position, newPosition);
            if (!moveResponse.ok) {
                const data = await moveResponse.json().catch(() => null);
                setError(data?.detail ?? 'Could not reorder photos. Please try again.');
                setPhotos([...compacted, ...remaining.slice(compacted.length)]);
                return;
            }
            compacted.push({ ...photo, position: newPosition });
        }
        setPhotos(compacted);
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
            const data = await response.json().catch(() => null);
            setError(data?.detail ?? 'Could not save your profile. Please check your details and try again.');
            setIsLoading(false);
            return;
        }

        if (latitude !== '' && longitude !== '') {
            const locationResponse = await updateLocation(Number(latitude), Number(longitude));
            if (!locationResponse.ok) {
                const data = await locationResponse.json().catch(() => null);
                setError(data?.detail ?? 'Profile saved, but we could not save your location. You can add it later.');
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
        photos,
        isUploadingPhoto,
        uploadPhoto,
        deletePhoto,
        error,
        isLoading,
        goNext,
        goBack,
        HandleUseLocation,
        handleBirthdateNext,
        handleFinish,
    };
}
