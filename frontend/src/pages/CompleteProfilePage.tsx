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

            <StepProgress step={step} />

            {step === 0 && (
                <GenderStep
                    key={step}
                    isActive
                    gender={gender}
                    setGender={setGender}
                    onNext={goNext}
                />
            )}

            {step === 1 && (
                <OrientationStep
                    key={step}
                    isActive
                    orientation={orientation}
                    setOrientation={setOrientation}
                    onBack={goBack}
                    onNext={goNext}
                />
            )}

            {step === 2 && (
                <BioStep
                    key={step}
                    isActive
                    bio={bio}
                    setBio={setBio}
                    onBack={goBack}
                    onNext={goNext}
                />
            )}

            {step === 3 && (
                <BirthdateStep
                    key={step}
                    isActive
                    birth_date={birth_date}
                    setBirthDate={setBirthDate}
                    onBack={goBack}
                    onNext={handleBirthdateNext}
                />
            )}

            {step === 4 && (
                <LocationStep
                    key={step}
                    isActive
                    city={city}
                    setCity={setCity}
                    latitude={latitude}
                    longitude={longitude}
                    onUseLocation={HandleUseLocation}
                    onBack={goBack}
                    onNext={handleFinish}
                    isLoading={isLoading}
                />
            )}

            <div className="mt-4">
                <FormNotice tone="error">{error}</FormNotice>
            </div>
        </AuthLayout>
    );
}
