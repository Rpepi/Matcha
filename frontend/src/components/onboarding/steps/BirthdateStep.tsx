import StepPanel from "../StepPanel";
import { Field } from "../../FormControls";

interface BirthdateStepProps {
    birth_date: string;
    setBirthDate: (value: string) => void;
    onBack: () => void;
    onNext: () => void;
}

export default function BirthdateStep({ birth_date, setBirthDate, onBack, onNext }: BirthdateStepProps) {
    return (
        <StepPanel
            title="When were you born?"
            nextDisabled={!birth_date}
            onBack={onBack}
            onNext={onNext}
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
