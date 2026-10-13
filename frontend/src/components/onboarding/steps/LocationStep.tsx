import StepPanel from "../StepPanel";
import LocationSearchField from "@/components/LocationSearchField";

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
    /** Changes when a position is found from the connection: the field starts over to show it. */
    fieldKey?: number;
}

export default function LocationStep({ city, latitude, longitude, onUseLocation, onSelectLocation, onClearLocation, onBack, onNext, isLoading, fieldKey }: LocationStepProps) {
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
            <LocationSearchField
                key={fieldKey}
                city={city}
                onUseLocation={onUseLocation}
                onSelectLocation={onSelectLocation}
                onClearLocation={onClearLocation}
            />
        </StepPanel>
    );
}
