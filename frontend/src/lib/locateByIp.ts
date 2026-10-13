import { approximateLocation, type ApproximateLocation } from "@/api/profile";

export interface Place {
    latitude: number;
    longitude: number;
    city: string | null;
}

/**
 * Rough position from the user's connection, found without asking them anything
 * (the fallback when they do not share their GPS position). Null when it cannot
 * be found: never an error for the caller to handle.
 */
export async function locateByIp(): Promise<Place | null> {
    try {
        const response = await approximateLocation();
        if (!response.ok) return null;
        const data = (await response.json()) as ApproximateLocation;
        return data.located ? { latitude: data.latitude, longitude: data.longitude, city: data.city } : null;
    } catch {
        return null;
    }
}
