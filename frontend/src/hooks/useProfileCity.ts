import { useCallback, useState } from "react";
import { useProfileContext } from "@/context/ProfileContext";
import { useToast } from "@/context/ToastContext";
import { updateProfile, updateLocation } from "@/api/profile";
import { reverseGeocode } from "@/lib/nominatim";

export function useProfileCity(city: string | null) {
    const { refetch } = useProfileContext();
    const { showError } = useToast();
    const [isEditing, setIsEditing] = useState(false);
    const [isSaving, setIsSaving] = useState(false);
    const [pendingCity, setPendingCity] = useState(city ?? "");
    const [latitude, setLatitude] = useState<number | "">("");
    const [longitude, setLongitude] = useState<number | "">("");

    const startEditing = useCallback(() => {
        setPendingCity(city ?? "");
        setLatitude("");
        setLongitude("");
        setIsEditing(true);
    }, [city]);

    const cancelEditing = useCallback(() => setIsEditing(false), []);

    const selectLocation = useCallback((selectedCity: string, lat: number, lon: number) => {
        setPendingCity(selectedCity);
        setLatitude(lat);
        setLongitude(lon);
    }, []);

    const clearLocation = useCallback(() => {
        setLatitude("");
        setLongitude("");
    }, []);

    const useMyLocation = useCallback((): Promise<string | null> => {
        return new Promise((resolve) => {
            if (!("geolocation" in navigator)) {
                showError("Your browser does not support geolocation");
                resolve(null);
                return;
            }
            navigator.geolocation.getCurrentPosition(
                async (position) => {
                    const lat = position.coords.latitude;
                    const lon = position.coords.longitude;
                    setLatitude(lat);
                    setLongitude(lon);
                    const cityName = await reverseGeocode(lat, lon);
                    if (cityName) setPendingCity(cityName);
                    resolve(cityName);
                },
                (geoError) => {
                    switch (geoError.code) {
                        case 1:
                            showError("Access to this location has been denied. Please allow it in your browser settings.");
                            break;
                        case 2:
                            showError("This location is not available. Please search for your city instead.");
                            break;
                        case 3:
                            showError("Geolocation took too long. Please try again or enter your city.");
                            break;
                        default:
                            showError("An unknown error occurred.");
                    }
                    resolve(null);
                },
                { timeout: 10000, maximumAge: 60000, enableHighAccuracy: false },
            );
        });
    }, [showError]);

    const canSave = latitude !== "" && longitude !== "";

    const save = useCallback(async () => {
        if (!canSave) return;
        setIsSaving(true);
        try {
            const cityResponse = await updateProfile({ city: pendingCity || null });
            if (!cityResponse.ok) {
                const data = await cityResponse.json().catch(() => null);
                showError(data?.detail ?? "Could not save your city. Please try again.");
                return;
            }

            const locationResponse = await updateLocation(latitude as number, longitude as number);
            if (!locationResponse.ok) {
                const data = await locationResponse.json().catch(() => null);
                showError(data?.detail ?? "City saved, but we could not save your location. Please try again.");
                return;
            }

            await refetch();
            setIsEditing(false);
        } catch {
            showError("Could not save your city. Please check your connection and try again.");
        } finally {
            setIsSaving(false);
        }
    }, [canSave, pendingCity, latitude, longitude, refetch, showError]);

    return { isEditing, isSaving, canSave, startEditing, cancelEditing, selectLocation, clearLocation, useMyLocation, save };
}
