import StepPanel from "../StepPanel";
import { Field } from "../../FormControls";

interface LocationStepProps {
    city: string;
    setCity: (value: string) => void;
    latitude: number | '';
    longitude: number | '';
    onUseLocation: () => void;
    onBack: () => void;
    onNext: () => void;
    isLoading: boolean;
}

export default function LocationStep({ city, setCity, latitude, longitude, onUseLocation, onBack, onNext, isLoading }: LocationStepProps) {
    return (
        <StepPanel
            title="Where are you?"
            subtitle="We use this to find matches nearby."
            onBack={onBack}
            onNext={onNext}
            nextLabel="Finish setting up"
            isLoading={isLoading}
        >
            <div className="mb-1.5 flex items-center justify-between">
                <span className="text-sm font-medium text-ink/80">City</span>
                <button
                    type="button"
                    onClick={onUseLocation}
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
                <p className="mt-1.5 text-xs text-ink/50">
                    Location detected ({Number(latitude).toFixed(2)}, {Number(longitude).toFixed(2)})
                </p>
            )}
        </StepPanel>
    );
}
