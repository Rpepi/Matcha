import LocationSearchField from "@/components/LocationSearchField";
import { useProfileCity } from "@/hooks/useProfileCity";
import { Button } from "@/components/FormControls";

export default function ProfileCity({ city }: { city: string | null }) {
    const { isEditing, isSaving, canSave, startEditing, cancelEditing, selectLocation, clearLocation, useMyLocation, save } =
        useProfileCity(city);

    return (
        <div className="flex flex-col gap-3">
            <div className="flex items-center justify-between">
                <h2 className="text-xs font-semibold tracking-widest text-grey uppercase">City</h2>
                {!isEditing && (
                    <button
                        type="button"
                        onClick={startEditing}
                        className="cursor-pointer rounded-full px-2.5 py-1 text-sm font-medium text-grey transition hover:bg-grey/10 hover:text-ink"
                    >
                        Edit
                    </button>
                )}
            </div>

            {isEditing ? (
                <div className="flex flex-col gap-3">
                    <LocationSearchField
                        city={city ?? ""}
                        onUseLocation={useMyLocation}
                        onSelectLocation={selectLocation}
                        onClearLocation={clearLocation}
                    />
                    <div className="flex gap-3">
                        <Button onClick={save} disabled={isSaving || !canSave} className="w-auto px-4 py-2 text-sm">
                            {isSaving ? "Saving..." : "Save"}
                        </Button>
                        <button
                            type="button"
                            onClick={cancelEditing}
                            disabled={isSaving}
                            className="cursor-pointer rounded-xl px-4 py-2 text-sm font-medium text-ink/70 transition hover:bg-grey/10 disabled:cursor-not-allowed disabled:opacity-60"
                        >
                            Cancel
                        </button>
                    </div>
                </div>
            ) : (
                <p className={city ? "text-ink" : "text-grey/50 italic"}>{city ?? "Empty"}</p>
            )}
        </div>
    );
}
