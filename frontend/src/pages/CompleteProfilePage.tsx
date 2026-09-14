import AuthLayout from "../components/AuthLayout";
import LoadingScreen from "../components/LoadingScreen";
import { FormNotice } from "../components/FormControls";
import { useOnboarding } from "../hooks/useOnboarding";
import StepProgress from "../components/onboarding/StepProgress";
import GenderStep from "../components/onboarding/steps/GenderStep";
import OrientationStep from "../components/onboarding/steps/OrientationStep";
import BioStep from "../components/onboarding/steps/BioStep";
import BirthdateStep from "../components/onboarding/steps/BirthdateStep";
import PhotosStep from "../components/onboarding/steps/PhotosStep";
import LocationStep from "../components/onboarding/steps/LocationStep";

export default function CompleteProfilePage() {
    const {
        step,
        isHydrating,
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
        photos,
        isUploadingPhoto,
        uploadPhoto,
        deletePhoto,
        error,
        isLoading,
        goNext,
        goBack,
        HandleUseLocation,
        handleGenderNext,
        handleOrientationNext,
        handleBioNext,
        handleBirthdateNext,
        handleFinish,
    } = useOnboarding();

    if (isHydrating) {
        return <LoadingScreen />;
    }

    return (
        <AuthLayout hideClose>

            <StepProgress step={step} />

            {step === 0 && (
                <GenderStep
                    key={step}
                    gender={gender}
                    setGender={setGender}
                    onNext={handleGenderNext}
                />
            )}

            {step === 1 && (
                <OrientationStep
                    key={step}
                    orientation={orientation}
                    setOrientation={setOrientation}
                    onBack={goBack}
                    onNext={handleOrientationNext}
                />
            )}

            {step === 2 && (
                <BioStep
                    key={step}
                    bio={bio}
                    setBio={setBio}
                    onBack={goBack}
                    onNext={handleBioNext}
                />
            )}

            {step === 3 && (
                <BirthdateStep
                    key={step}
                    birth_date={birth_date}
                    setBirthDate={setBirthDate}
                    onBack={goBack}
                    onNext={handleBirthdateNext}
                />
            )}

            {step === 4 && (
                <PhotosStep
                    key={step}
                    photos={photos}
                    isUploading={isUploadingPhoto}
                    onUpload={uploadPhoto}
                    onDelete={deletePhoto}
                    onBack={goBack}
                    onNext={goNext}
                />
            )}

            {step === 5 && (
                <LocationStep
                    key={step}
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
