import StepPanel from "../StepPanel";
import { SelectField } from "../../FormControls";
import { interestedInOptions } from "../../../lib/orientation";

interface OrientationStepProps {
    // Picked on the previous step: the options read differently for each gender
    gender: string;
    orientation: string;
    setOrientation: (value: string) => void;
    onBack: () => void;
    onNext: () => void;
}

export default function OrientationStep({ gender, orientation, setOrientation, onBack, onNext }: OrientationStepProps) {
    return (
        <StepPanel
            title="Who would you like to meet?"
            nextDisabled={!orientation}
            onBack={onBack}
            onNext={onNext}
        >
            <SelectField
                id="orientation"
                value={orientation}
                onChange={(e) => setOrientation(e.target.value)}
            >
                <option value="" disabled>Choose one</option>
                {interestedInOptions(gender).map(({ value, label }) => (
                    <option key={value} value={value}>{label}</option>
                ))}
            </SelectField>
        </StepPanel>
    );
}
