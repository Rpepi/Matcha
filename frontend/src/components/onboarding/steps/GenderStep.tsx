import StepPanel from "../StepPanel";
import { SelectField } from "../../FormControls";

interface GenderStepProps {
    isActive: boolean;
    gender: string;
    setGender: (value: string) => void;
    onNext: () => void;
}

export default function GenderStep({ isActive, gender, setGender, onNext }: GenderStepProps) {
    return (
        <StepPanel
            title="What's your gender?"
            nextDisabled={!gender}
            onNext={onNext}
            isActive={isActive}
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
