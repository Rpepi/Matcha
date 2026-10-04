import { useState, useEffect, useRef } from "react";
import { useNavigate } from "react-router-dom";
import { useProfileContext } from "../context/ProfileContext";
import { updateProfile, updateLocation } from "../api/profile";
import { uploadPhoto as uploadPhotoApi, deletePhoto as deletePhotoApi, movePhoto as movePhotoApi } from "../api/photos";
import { updateTags } from "../api/tags";
import { reverseGeocode } from "../lib/nominatim";

export const STEP_COUNT = 7;

export interface OnboardingPhoto {
    position: number;
    url: string | null; // null for a photo restored from the server (no local file to preview)
}

export function useOnboarding() {
    const { status, profile, refetch } = useProfileContext();
    const hasHydrated = useRef(false);
    const [step, setStep] = useState(0);
    const [isHydrating, setIsHydrating] = useState(true);
    const [firstName, setFirstName] = useState('');

    const [gender, setGender] = useState('');
    const [orientation, setOrientation] = useState('');
    const [bio, setBio] = useState('');
    const [tags, setTags] = useState<string[]>([]);
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
        if (status === 'loading' || hasHydrated.current || !profile) return;
        hasHydrated.current = true;

        setFirstName(profile.first_name ?? '');
        setGender(profile.gender ?? '');
        setOrientation(profile.orientation ?? '');
        setBio(profile.bio ?? '');
        if (Array.isArray(profile.tags)) setTags(profile.tags);
        setBirthDate(profile.birth_date ?? '');
        setCity(profile.city ?? '');
        setLatitude(profile.latitude ?? '');
        setLongitude(profile.longitude ?? '');
        if (Array.isArray(profile.photos)) {
            setPhotos(
                profile.photos
                    .map((p): OnboardingPhoto => ({ position: p.position, url: `/api/profile/photos/${p.position}?v=${encodeURIComponent(p.path)}` }))
                    .sort((a, b) => a.position - b.position)
            );
        }
        setIsHydrating(false);
    }, [status, profile]);

    function goNext() {
        setError('');
        setStep((s) => Math.min(s + 1, STEP_COUNT - 1));
    }

    function goBack() {
        setError('');
        setStep((s) => Math.max(s - 1, 0));
    }

    async function saveStep(fields: Parameters<typeof updateProfile>[0]): Promise<boolean> {
        setError('');
        const response = await updateProfile(fields);
        if (!response.ok) {
            const data = await response.json().catch(() => null);
            setError(data?.detail ?? 'Could not save. Please try again.');
            return false;
        }
        return true;
    }

    async function handleGenderNext() {
        if (await saveStep({ gender })) goNext();
    }

    async function handleOrientationNext() {
        if (await saveStep({ orientation })) goNext();
    }

    async function handleBioNext() {
        if (await saveStep({ bio })) goNext();
    }

    async function handleTagsNext() {
        setError('');
        const response = await updateTags(tags);
        if (!response.ok) {
            const data = await response.json().catch(() => null);
            setError(data?.detail ?? 'Could not save your tags. Please try again.');
            return;
        }
        goNext();
    }

    function HandleUseLocation(): Promise<string | null> {
        return new Promise((resolve) => {
            if (!("geolocation" in navigator)) {
                setError("Your browser does not support geolocation");
                resolve(null);
                return;
            }
            navigator.geolocation.getCurrentPosition(async (position) => {
                const lat = position.coords.latitude;
                const lon = position.coords.longitude;
                setLatitude(lat);
                setLongitude(lon);
                const cityName = await reverseGeocode(lat, lon);
                if (cityName) setCity(cityName);
                resolve(cityName);
            },
            (geoError) => {
                switch (geoError.code) {
                    case 1:
                        setError("Access to this location has been denied. Please allow it in your browser settings.");
                        break;
                    case 2:
                        setError("This location is not available. Please search for your city instead.");
                        break;
                    case 3:
                        setError("Geolocation took too long. Please try again or enter your city.");
                        break;
                    default:
                        setError("An unknown error occurred.");
                }
                resolve(null);
            },
            {
                timeout: 10000,
                maximumAge: 60000,
                enableHighAccuracy: false,
            })
        });
    }

    function handleSelectLocation(selectedCity: string, lat: number, lon: number) {
        setCity(selectedCity);
        setLatitude(lat);
        setLongitude(lon);
    }

    function handleClearLocation() {
        setLatitude('');
        setLongitude('');
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

    async function handleBirthdateNext() {
        if (!isAtLeast16(birth_date)) {
            setError("You must be at least 16 years old to use Matcha.");
            return;
        }
        if (await saveStep({ birth_date })) goNext();
    }

    async function handleFinish() {
        if (latitude === '' || longitude === '') {
            setError("Pick your city from the search, or share your location, so we can find matches near you.");
            return;
        }
        setError('');
        setIsLoading(true);

        const response = await updateProfile({ city: city || null });
        if (!response.ok) {
            const data = await response.json().catch(() => null);
            setError(data?.detail ?? 'Could not save your profile. Please check your details and try again.');
            setIsLoading(false);
            return;
        }

        const locationResponse = await updateLocation(latitude, longitude);
        if (!locationResponse.ok) {
            const data = await locationResponse.json().catch(() => null);
            setError(data?.detail ?? 'Profile saved, but we could not save your location. You can add it later.');
            setIsLoading(false);
            return;
        }

        await refetch();
        navigate('/browse');
    }

    return {
        step,
        isHydrating,
        firstName,
        gender,
        setGender,
        orientation,
        setOrientation,
        bio,
        setBio,
        tags,
        setTags,
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
        handleSelectLocation,
        handleClearLocation,
        handleGenderNext,
        handleOrientationNext,
        handleBioNext,
        handleTagsNext,
        handleBirthdateNext,
        handleFinish,
    };
}
