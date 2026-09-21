import StepPanel from "../StepPanel";
import { SelectField } from "../../FormControls";

interface GenderStepProps {
    gender: string;
    setGender: (value: string) => void;
    onNext: () => void;
}

export default function GenderStep({ gender, setGender, onNext }: GenderStepProps) {
    return (
        <StepPanel
            title="What's your gender?"
            nextDisabled={!gender}
            onNext={onNext}
        >
            <SelectField
                id="gender"
                value={gender}
                onChange={(e) => setGender(e.target.value)}
            >
                <option value="" disabled>Choose one</option>
                <option value="male">Male</option>
                <option value="female">Female</option>
                <option value="other">Other</option>
            </SelectField>
        </StepPanel>
    );
}
