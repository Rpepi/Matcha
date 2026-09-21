import AuthLayout from "../components/AuthLayout";
import LoadingScreen from "../components/LoadingScreen";
import { FormNotice } from "../components/FormControls";
import { useOnboarding } from "../hooks/useOnboarding";
import StepProgress from "../components/onboarding/StepProgress";
import GenderStep from "../components/onboarding/steps/GenderStep";
import OrientationStep from "../components/onboarding/steps/OrientationStep";
import BioStep from "../components/onboarding/steps/BioStep";
import TagsStep from "../components/onboarding/steps/TagsStep";
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
        tags,
        setTags,
        birth_date,
        setBirthDate,
        latitude,
        longitude,
        city,
        photos,
        isUploadingPhoto,
        uploadPhoto,
        deletePhoto,
        error,
        isLoading,
        goNext,
        goBack,
        HandleUseLocation,
        handleSelectLocation,
        handleClearLocation,
        handleGenderNext,
        handleOrientationNext,
        handleBioNext,
        handleTagsNext,
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
                <TagsStep
                    key={step}
                    tags={tags}
                    setTags={setTags}
                    onBack={goBack}
                    onNext={handleTagsNext}
                />
            )}

            {step === 4 && (
                <BirthdateStep
                    key={step}
                    birth_date={birth_date}
                    setBirthDate={setBirthDate}
                    onBack={goBack}
                    onNext={handleBirthdateNext}
                />
            )}

            {step === 5 && (
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

            {step === 6 && (
                <LocationStep
                    key={step}
                    city={city}
                    latitude={latitude}
                    longitude={longitude}
                    onUseLocation={HandleUseLocation}
                    onSelectLocation={handleSelectLocation}
                    onClearLocation={handleClearLocation}
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
