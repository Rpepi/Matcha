import StepPanel from "../StepPanel";
import { SelectField } from "../../FormControls";

interface OrientationStepProps {
    isActive: boolean;
    orientation: string;
    setOrientation: (value: string) => void;
    onBack: () => void;
    onNext: () => void;
}

export default function OrientationStep({ isActive, orientation, setOrientation, onBack, onNext }: OrientationStepProps) {
    return (
        <StepPanel
            title="Who are you interested in?"
            nextDisabled={!orientation}
            onBack={onBack}
            onNext={onNext}
            isActive={isActive}
        >
            <SelectField
                id="orientation"
                value={orientation}
                onChange={(e) => setOrientation(e.target.value)}
            >
                <option value="" disabled>Choose one</option>
                <option value="hetero">Hetero</option>
                <option value="homo">Homo</option>
                <option value="bi">Bi</option>
            </SelectField>
        </StepPanel>
    );
}
