import AuthLayout from "../components/AuthLayout";
import { FormNotice } from "../components/FormControls";
import { useOnboarding } from "../hooks/useOnboarding";
import StepProgress from "../components/onboarding/StepProgress";
import GenderStep from "../components/onboarding/steps/GenderStep";
import OrientationStep from "../components/onboarding/steps/OrientationStep";
import BioStep from "../components/onboarding/steps/BioStep";
import BirthdateStep from "../components/onboarding/steps/BirthdateStep";
import LocationStep from "../components/onboarding/steps/LocationStep";

export default function CompleteProfilePage() {
    const {
        step,
        firstName,
        gender,
        setGender,
        orientation,
        setOrientation,
        bio,
        setBio,
        birth_date,
        setBirthDate,
        latitude,
        longitude,
        city,
        setCity,
        error,
        isLoading,
        goNext,
        goBack,
        HandleUseLocation,
        handleBirthdateNext,
        handleFinish,
    } = useOnboarding();

    return (
        <AuthLayout>
            <h2 className="font-display text-2xl font-medium text-plum">
                {firstName ? `Welcome, ${firstName}.` : "Let's finish setting you up."}
            </h2>
            <p className="mt-1.5 mb-6 text-sm text-plum/60">
                A handful of quick questions, then you're ready to start matching.
            </p>

            <StepProgress step={step} />

            <div className="overflow-hidden">
                <div
                    className="flex transition-transform duration-300 ease-in-out motion-reduce:transition-none"
                    style={{ transform: `translateX(-${step * 100}%)` }}
                >
                    <GenderStep
                        isActive={step === 0}
                        gender={gender}
                        setGender={setGender}
                        onNext={goNext}
                    />

                    <OrientationStep
                        isActive={step === 1}
                        orientation={orientation}
                        setOrientation={setOrientation}
                        onBack={goBack}
                        onNext={goNext}
                    />

                    <BioStep
                        isActive={step === 2}
                        bio={bio}
                        setBio={setBio}
                        onBack={goBack}
                        onNext={goNext}
                    />

                    <BirthdateStep
                        isActive={step === 3}
                        birth_date={birth_date}
                        setBirthDate={setBirthDate}
                        onBack={goBack}
                        onNext={handleBirthdateNext}
                    />

                    <LocationStep
                        isActive={step === 4}
                        city={city}
                        setCity={setCity}
                        latitude={latitude}
                        longitude={longitude}
                        onUseLocation={HandleUseLocation}
                        onBack={goBack}
                        onNext={handleFinish}
                        isLoading={isLoading}
                    />
                </div>
            </div>

            <div className="mt-4">
                <FormNotice tone="error">{error}</FormNotice>
            </div>
        </AuthLayout>
    );
}
