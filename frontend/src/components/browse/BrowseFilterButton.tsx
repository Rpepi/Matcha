import { useState, type ReactNode } from "react";
import { Dialog } from "@base-ui/react/dialog";
import { Slider } from "@base-ui/react/slider";
import { SlidersHorizontal } from "lucide-react";
import { useBrowseContext } from "@/context/BrowseContext";
import { useProfileContext } from "@/context/ProfileContext";
import { Button, fieldClasses } from "@/components/FormControls";
import { getAvailableTags } from "@/api/tags";
import {
    AGE_MIN, AGE_MAX, DISTANCE_MAX_KM, FAME_MAX, TAGS_MAX, NAMED_TAGS_MAX, DEFAULT_FILTERS, SORT_OPTIONS,
    type BrowseFilters, type BrowseSort,
} from "@/lib/browseFilters";

const sliderTrackClasses = "relative h-1.5 w-full grow cursor-pointer rounded-full bg-grey/20";
const sliderIndicatorClasses = "absolute h-full rounded-full bg-matcha";
const sliderThumbClasses =
    "h-5 w-5 cursor-pointer rounded-full border-2 border-matcha bg-paper shadow outline-none transition focus-visible:ring-2 focus-visible:ring-matcha/50";

function FilterSection({ label, value, children }: { label: string; value: string; children: ReactNode }) {
    return (
        <div className="flex flex-col gap-3">
            <div className="flex items-baseline justify-between">
                <span className="text-sm font-medium text-ink">{label}</span>
                <span className="text-sm text-grey">{value}</span>
            </div>
            {children}
        </div>
    );
}

export default function BrowseFilterButton() {
    const { filters, applyFilters } = useBrowseContext();
    const { profile } = useProfileContext();
    const [open, setOpen] = useState(false);
    const [draft, setDraft] = useState<BrowseFilters>(filters);
    // The tag vocabulary is loaded the first time the dialog opens, then kept.
    const [availableTags, setAvailableTags] = useState<string[] | null>(null);
    const [tagsFailed, setTagsFailed] = useState(false);

    const tagsMax = Math.min(profile?.tags.length ?? 0, TAGS_MAX);

    function loadTags() {
        setTagsFailed(false);
        getAvailableTags()
            .then(async (response) => {
                const data = response.ok ? await response.json() : null;
                if (!Array.isArray(data?.tags)) throw new Error("no tags");
                setAvailableTags(data.tags);
            })
            .catch(() => setTagsFailed(true));
    }

    function handleOpenChange(next: boolean) {
        if (next) {
            setDraft({ ...filters, minTags: Math.min(filters.minTags, tagsMax) });
            if (availableTags === null) loadTags();
        }
        setOpen(next);
    }

    function toggleTag(tag: string) {
        setDraft((prev) => {
            if (prev.tags.includes(tag)) return { ...prev, tags: prev.tags.filter((t) => t !== tag) };
            if (prev.tags.length >= NAMED_TAGS_MAX) return prev;
            return { ...prev, tags: [...prev.tags, tag] };
        });
    }

    function changeSort(sort: BrowseSort) {
        // Each sort starts in its usual direction; the second menu can flip it.
        setDraft((prev) => ({ ...prev, sort, order: SORT_OPTIONS[sort].defaultOrder }));
    }

    return (
        <Dialog.Root open={open} onOpenChange={handleOpenChange}>
            <Dialog.Trigger className="mb-6 flex cursor-pointer items-center gap-2 rounded-full bg-grey/10 px-5 py-2 text-sm font-medium text-ink transition hover:bg-matcha/25">
                <SlidersHorizontal className="h-4 w-4" />
                Filters
            </Dialog.Trigger>

            <Dialog.Portal>
                <Dialog.Backdrop className="fixed inset-0 z-50 bg-ink/50 transition-opacity duration-150 data-[ending-style]:opacity-0 data-[starting-style]:opacity-0" />
                <Dialog.Popup className="fixed top-1/2 left-1/2 z-50 max-h-[calc(100dvh-2.5rem)] w-[calc(100%-2.5rem)] max-w-md -translate-x-1/2 -translate-y-1/2 overflow-y-auto rounded-2xl bg-white p-6 shadow-xl shadow-ink/20 outline-none transition-all duration-150 data-[ending-style]:scale-95 data-[ending-style]:opacity-0 data-[starting-style]:scale-95 data-[starting-style]:opacity-0">
                    <Dialog.Title className="font-display text-xl font-medium text-ink">
                        Filter suggestions
                    </Dialog.Title>

                    <div className="mt-6 flex flex-col gap-6">
                        <FilterSection label="Age" value={`${draft.minAge} – ${draft.maxAge}`}>
                            <Slider.Root
                                value={[draft.minAge, draft.maxAge]}
                                onValueChange={([minAge, maxAge]) => setDraft((prev) => ({ ...prev, minAge, maxAge }))}
                                min={AGE_MIN}
                                max={AGE_MAX}
                            >
                                <Slider.Control className="flex w-full items-center py-2">
                                    <Slider.Track className={sliderTrackClasses}>
                                        <Slider.Indicator className={sliderIndicatorClasses} />
                                        <Slider.Thumb className={sliderThumbClasses} index={0} />
                                        <Slider.Thumb className={sliderThumbClasses} index={1} />
                                    </Slider.Track>
                                </Slider.Control>
                            </Slider.Root>
                        </FilterSection>

                        <FilterSection
                            label="Distance"
                            value={draft.maxDistance >= DISTANCE_MAX_KM ? "Any" : `Up to ${draft.maxDistance} km`}
                        >
                            <Slider.Root
                                value={draft.maxDistance}
                                onValueChange={(maxDistance) => setDraft((prev) => ({ ...prev, maxDistance }))}
                                min={1}
                                max={DISTANCE_MAX_KM}
                            >
                                <Slider.Control className="flex w-full items-center py-2">
                                    <Slider.Track className={sliderTrackClasses}>
                                        <Slider.Indicator className={sliderIndicatorClasses} />
                                        <Slider.Thumb className={sliderThumbClasses} />
                                    </Slider.Track>
                                </Slider.Control>
                            </Slider.Root>
                        </FilterSection>

                        <FilterSection
                            label="Fame rating"
                            value={
                                draft.minFame === 0 && draft.maxFame >= FAME_MAX
                                    ? "Any"
                                    : `${draft.minFame} – ${draft.maxFame >= FAME_MAX ? "max" : draft.maxFame}`
                            }
                        >
                            <Slider.Root
                                value={[draft.minFame, draft.maxFame]}
                                onValueChange={([minFame, maxFame]) => setDraft((prev) => ({ ...prev, minFame, maxFame }))}
                                min={0}
                                max={FAME_MAX}
                            >
                                <Slider.Control className="flex w-full items-center py-2">
                                    <Slider.Track className={sliderTrackClasses}>
                                        <Slider.Indicator className={sliderIndicatorClasses} />
                                        <Slider.Thumb className={sliderThumbClasses} index={0} />
                                        <Slider.Thumb className={sliderThumbClasses} index={1} />
                                    </Slider.Track>
                                </Slider.Control>
                            </Slider.Root>
                        </FilterSection>

                        {tagsMax === 0 ? (
                            <div className="flex flex-col gap-3">
                                <span className="text-sm font-medium text-ink">Shared interests</span>
                                <p className="text-sm text-grey">Add tags to your profile to filter by shared interests.</p>
                            </div>
                        ) : (
                            <FilterSection
                                label="Shared interests"
                                value={draft.minTags === 0 ? "Any" : `At least ${draft.minTags}`}
                            >
                                <Slider.Root
                                    value={draft.minTags}
                                    onValueChange={(minTags) => setDraft((prev) => ({ ...prev, minTags }))}
                                    min={0}
                                    max={tagsMax}
                                >
                                    <Slider.Control className="flex w-full items-center py-2">
                                        <Slider.Track className={sliderTrackClasses}>
                                            <Slider.Indicator className={sliderIndicatorClasses} />
                                            <Slider.Thumb className={sliderThumbClasses} />
                                        </Slider.Track>
                                    </Slider.Control>
                                </Slider.Root>
                            </FilterSection>
                        )}

                        <FilterSection
                            label="Specific interests"
                            value={draft.tags.length === 0 ? "Any" : `${draft.tags.length} of ${NAMED_TAGS_MAX} chosen`}
                        >
                            {tagsFailed ? (
                                <p className="text-sm text-grey">
                                    Could not load the interests.{" "}
                                    <button type="button" onClick={loadTags} className="cursor-pointer font-medium text-ink underline">
                                        Try again
                                    </button>
                                </p>
                            ) : availableTags === null ? (
                                <p className="text-sm text-grey">Loading interests…</p>
                            ) : (
                                <div className="flex flex-wrap gap-2" role="group" aria-label="Interests every profile must have">
                                    {availableTags.map((tag) => {
                                        const selected = draft.tags.includes(tag);
                                        const full = !selected && draft.tags.length >= NAMED_TAGS_MAX;
                                        return (
                                            <button
                                                key={tag}
                                                type="button"
                                                aria-pressed={selected}
                                                disabled={full}
                                                onClick={() => toggleTag(tag)}
                                                className={`cursor-pointer rounded-full px-3 py-1 text-sm font-medium transition disabled:cursor-not-allowed disabled:opacity-40 ${
                                                    selected ? "bg-matcha text-ink" : "bg-grey/10 text-ink/80 hover:bg-matcha/25"
                                                }`}
                                            >
                                                {tag}
                                            </button>
                                        );
                                    })}
                                </div>
                            )}
                        </FilterSection>

                        <div className="flex flex-col gap-3">
                            <span className="text-sm font-medium text-ink">Sort by</span>
                            <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
                                <select
                                    aria-label="Sort by"
                                    className={fieldClasses}
                                    value={draft.sort}
                                    onChange={(e) => changeSort(e.target.value as BrowseSort)}
                                >
                                    {(Object.keys(SORT_OPTIONS) as BrowseSort[]).map((sort) => (
                                        <option key={sort} value={sort}>
                                            {SORT_OPTIONS[sort].label}
                                        </option>
                                    ))}
                                </select>
                                <select
                                    aria-label="Order"
                                    className={fieldClasses}
                                    value={draft.order}
                                    onChange={(e) => setDraft((prev) => ({ ...prev, order: e.target.value as BrowseFilters["order"] }))}
                                >
                                    <option value="asc">{SORT_OPTIONS[draft.sort].asc}</option>
                                    <option value="desc">{SORT_OPTIONS[draft.sort].desc}</option>
                                </select>
                            </div>
                        </div>
                    </div>

                    <div className="mt-8 flex items-center gap-4">
                        <button
                            type="button"
                            onClick={() => setDraft(DEFAULT_FILTERS)}
                            className="cursor-pointer text-sm font-medium text-grey transition hover:text-ink"
                        >
                            Reset
                        </button>
                        <div className="flex-1">
                            <Dialog.Close
                                render={<Button type="button" onClick={() => applyFilters(draft)} />}
                            >
                                Apply filters
                            </Dialog.Close>
                        </div>
                    </div>
                </Dialog.Popup>
            </Dialog.Portal>
        </Dialog.Root>
    );
}
