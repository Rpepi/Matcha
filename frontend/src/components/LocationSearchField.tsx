import { useState, useEffect, useRef } from "react";
import { Field } from "@/components/FormControls";
import { formatPlaceLabel, type NominatimResult } from "@/lib/nominatim";

interface LocationSearchFieldProps {
    city: string;
    onUseLocation: () => Promise<string | null>;
    onSelectLocation: (city: string, latitude: number, longitude: number) => void;
    onClearLocation: () => void;
    label?: string;
    /** The button next to the label; `onUseLocation` resolves with the text to show (null keeps the current text). */
    actionLabel?: string;
    placeholder?: string;
}

export default function LocationSearchField({
    city,
    onUseLocation,
    onSelectLocation,
    onClearLocation,
    label = "City or neighborhood",
    actionLabel = "Use my position",
    placeholder = "Search for your city or neighborhood",
}: LocationSearchFieldProps) {
    const [query, setQuery] = useState(city);
    const [suggestions, setSuggestions] = useState<NominatimResult[]>([]);
    const [isSearching, setIsSearching] = useState(false);
    const [showSuggestions, setShowSuggestions] = useState(false);
    const [isLocating, setIsLocating] = useState(false);
    // The text of the place currently chosen (given, picked or located): showing it is not a search.
    // Without this, a field opened with a city already in it searched for it straight away and popped
    // the suggestions open over the buttons below. Not cleared once used: React's development mode
    // runs the effect twice, and the second run must not search either.
    const chosenText = useRef(city);
    const containerRef = useRef<HTMLDivElement>(null);

    useEffect(() => {
        if (query === chosenText.current) {
            setSuggestions([]);
            return;
        }
        if (query.trim().length < 3) {
            setSuggestions([]);
            return;
        }
        const controller = new AbortController();
        const timeout = setTimeout(() => {
            setIsSearching(true);
            fetch(`https://nominatim.openstreetmap.org/search?format=json&addressdetails=1&q=${encodeURIComponent(query)}&limit=5`, {
                signal: controller.signal,
            })
                .then((res) => res.json())
                .then((data: NominatimResult[]) => {
                    setSuggestions(data);
                    setShowSuggestions(true);
                })
                .catch((err) => {
                    if (err.name !== "AbortError") setSuggestions([]);
                })
                .finally(() => {
                    if (!controller.signal.aborted) setIsSearching(false);
                });
        }, 500);
        return () => {
            clearTimeout(timeout);
            controller.abort();
        };
    }, [query]);

    useEffect(() => {
        function handleClickOutside(e: MouseEvent) {
            if (containerRef.current && !containerRef.current.contains(e.target as Node)) {
                setShowSuggestions(false);
            }
        }
        document.addEventListener("mousedown", handleClickOutside);
        return () => document.removeEventListener("mousedown", handleClickOutside);
    }, []);

    function handleSelect(result: NominatimResult) {
        const label = formatPlaceLabel(result);
        chosenText.current = label;
        setQuery(label);
        setShowSuggestions(false);
        setSuggestions([]);
        onSelectLocation(label, parseFloat(result.lat), parseFloat(result.lon));
    }

    async function handleUseLocationClick() {
        setIsLocating(true);
        const cityName = await onUseLocation();
        if (cityName !== null) {
            chosenText.current = cityName;
            setQuery(cityName);
            setShowSuggestions(false);
        }
        setIsLocating(false);
    }

    return (
        <div>
            <div className="mb-1.5 flex items-center justify-between">
                <span className="text-sm font-medium text-ink/80">{label}</span>
                <button
                    type="button"
                    onClick={handleUseLocationClick}
                    disabled={isLocating}
                    className="text-xs font-medium text-orchid hover:underline disabled:opacity-50"
                >
                    {isLocating ? "Locating…" : actionLabel}
                </button>
            </div>
            <div ref={containerRef} className="relative">
                <Field
                    id="city"
                    type="text"
                    placeholder={placeholder}
                    value={query}
                    onChange={(e) => {
                        setQuery(e.target.value);
                        setShowSuggestions(true);
                        onClearLocation();
                    }}
                    onFocus={() => { if (suggestions.length > 0) setShowSuggestions(true); }}
                    autoComplete="off"
                />
                {showSuggestions && (suggestions.length > 0 || isSearching) && (
                    <div className="absolute z-20 mt-1 w-full rounded-xl border border-grey/30 bg-paper py-1 shadow-lg">
                        {isSearching && (
                            <div className="px-3 py-2 text-sm text-ink/50">Searching…</div>
                        )}
                        {!isSearching && suggestions.map((result) => (
                            <button
                                key={result.place_id}
                                type="button"
                                onMouseDown={() => handleSelect(result)}
                                className="block w-full truncate px-3 py-2 text-left text-sm text-ink/80 hover:bg-matcha/10"
                            >
                                {result.display_name}
                            </button>
                        ))}
                    </div>
                )}
            </div>
        </div>
    );
}
