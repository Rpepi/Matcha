import { useState, useEffect, useRef } from "react";
import StepPanel from "../StepPanel";
import { Field } from "../../FormControls";
import { formatPlaceLabel, type NominatimResult } from "../../../lib/nominatim";

interface LocationStepProps {
    city: string;
    latitude: number | '';
    longitude: number | '';
    onUseLocation: () => Promise<string | null>;
    onSelectLocation: (city: string, latitude: number, longitude: number) => void;
    onClearLocation: () => void;
    onBack: () => void;
    onNext: () => void;
    isLoading: boolean;
}

export default function LocationStep({ city, latitude, longitude, onUseLocation, onSelectLocation, onClearLocation, onBack, onNext, isLoading }: LocationStepProps) {
    const [query, setQuery] = useState(city);
    const [suggestions, setSuggestions] = useState<NominatimResult[]>([]);
    const [isSearching, setIsSearching] = useState(false);
    const [showSuggestions, setShowSuggestions] = useState(false);
    const [isLocating, setIsLocating] = useState(false);
    const skipNextSearch = useRef(false);
    const containerRef = useRef<HTMLDivElement>(null);

    useEffect(() => {
        if (skipNextSearch.current) {
            skipNextSearch.current = false;
            return;
        }
        if (query.trim().length < 3) {
            setSuggestions([]);
            return;
        }
        const timeout = setTimeout(() => {
            setIsSearching(true);
            fetch(`https://nominatim.openstreetmap.org/search?format=json&addressdetails=1&q=${encodeURIComponent(query)}&limit=5`)
                .then((res) => res.json())
                .then((data: NominatimResult[]) => {
                    setSuggestions(data);
                    setShowSuggestions(true);
                })
                .catch(() => setSuggestions([]))
                .finally(() => setIsSearching(false));
        }, 500);
        return () => clearTimeout(timeout);
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
        skipNextSearch.current = true;
        setQuery(label);
        setShowSuggestions(false);
        setSuggestions([]);
        onSelectLocation(label, parseFloat(result.lat), parseFloat(result.lon));
    }

    async function handleUseLocationClick() {
        setIsLocating(true);
        const cityName = await onUseLocation();
        if (cityName) {
            skipNextSearch.current = true;
            setQuery(cityName);
            setShowSuggestions(false);
        }
        setIsLocating(false);
    }

    return (
        <StepPanel
            title="Where are you?"
            subtitle="We use this to find matches nearby."
            nextDisabled={latitude === '' || longitude === ''}
            onBack={onBack}
            onNext={onNext}
            nextLabel="Finish setting up"
            isLoading={isLoading}
        >
            <div className="mb-1.5 flex items-center justify-between">
                <span className="text-sm font-medium text-ink/80">City or neighborhood</span>
                <button
                    type="button"
                    onClick={handleUseLocationClick}
                    disabled={isLocating}
                    className="text-xs font-medium text-orchid hover:underline disabled:opacity-50"
                >
                    {isLocating ? "Locating…" : "Use my position"}
                </button>
            </div>
            <div ref={containerRef} className="relative">
                <Field
                    id="city"
                    type="text"
                    placeholder="Search for your city or neighborhood"
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
        </StepPanel>
    );
}
