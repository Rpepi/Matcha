import StepPanel from "../StepPanel";
import { Field } from "../../FormControls";

interface BirthdateStepProps {
    isActive: boolean;
    birth_date: string;
    setBirthDate: (value: string) => void;
    onBack: () => void;
    onNext: () => void;
}

export default function BirthdateStep({ isActive, birth_date, setBirthDate, onBack, onNext }: BirthdateStepProps) {
    return (
        <StepPanel
            title="When were you born?"
            nextDisabled={!birth_date}
            onBack={onBack}
            onNext={onNext}
            isActive={isActive}
        >
            <Field
                id="birthdate"
                type="date"
                value={birth_date}
                onChange={(e) => setBirthDate(e.target.value)}
            />
        </StepPanel>
    );
}
