export interface NominatimAddress {
    neighbourhood?: string;
    suburb?: string;
    city_district?: string;
    city?: string;
    town?: string;
    village?: string;
    municipality?: string;
    country?: string;
}

export interface NominatimResult {
    place_id: number;
    display_name: string;
    lat: string;
    lon: string;
    address?: NominatimAddress;
}

const MAX_CITY_LENGTH = 100;

// Builds a short "neighborhood, city, country"-style label instead of Nominatim's
// full display_name, which routinely exceeds the backend's city VARCHAR(100) column.
export function formatPlaceLabel(result: NominatimResult): string {
    const { address, display_name } = result;
    const fallback = display_name.length > 90 ? `${display_name.slice(0, 90)}…` : display_name;

    if (!address) return fallback;

    const local = address.neighbourhood ?? address.suburb ?? address.city_district
        ?? address.city ?? address.town ?? address.village ?? address.municipality;
    const cityLevel = address.city ?? address.town ?? address.village ?? address.municipality;
    const parts = [local, cityLevel, address.country].filter((p): p is string => Boolean(p));
    const label = [...new Set(parts)].join(', ');

    return label && label.length <= MAX_CITY_LENGTH ? label : fallback;
}

export async function reverseGeocode(lat: number, lon: number): Promise<string | null> {
    try {
        const res = await fetch(`https://nominatim.openstreetmap.org/reverse?format=json&lat=${lat}&lon=${lon}&zoom=14`);
        const data: NominatimResult = await res.json();
        return data?.display_name ? formatPlaceLabel(data) : null;
    } catch {
        return null;
    }
}
