import StepPanel from "../StepPanel";
import { Field } from "../../FormControls";

interface BioStepProps {
    bio: string;
    setBio: (value: string) => void;
    onBack: () => void;
    onNext: () => void;
}

export default function BioStep({ bio, setBio, onBack, onNext }: BioStepProps) {
    return (
        <StepPanel
            title="Tell us about yourself"
            subtitle="Optional — you can always add this later."
            onBack={onBack}
            onNext={onNext}
            nextLabel={bio ? "Continue" : "Skip for now"}
        >
            <Field
                id="bio"
                type="text"
                placeholder="A line about you"
                value={bio}
                onChange={(e) => setBio(e.target.value)}
                maxLength={500}
            />
        </StepPanel>
    );
}
