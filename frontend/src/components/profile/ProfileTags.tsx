import { useState } from "react";
import { Menu } from "@base-ui/react/menu";
import { Loader2, Plus, X } from "lucide-react";
import { useProfileContext } from "@/context/ProfileContext";
import { useToast } from "@/context/ToastContext";
import { getAvailableTags, updateTags } from "@/api/tags";

const MAX_TAGS = 5;

export default function ProfileTags({ tags }: { tags: string[] }) {
    const { refetch } = useProfileContext();
    const { showError } = useToast();
    const [availableTags, setAvailableTags] = useState<string[]>([]);
    const [isLoadingTags, setIsLoadingTags] = useState(false);
    const [isSaving, setIsSaving] = useState(false);

    async function save(nextTags: string[]) {
        setIsSaving(true);
        const response = await updateTags(nextTags);
        setIsSaving(false);
        if (!response.ok) {
            const data = await response.json().catch(() => null);
            showError(data?.detail ?? "Could not save your interests. Please try again.");
            return;
        }
        await refetch();
    }

    function removeTag(tag: string) {
        void save(tags.filter((t) => t !== tag));
    }

    function addTag(tag: string) {
        void save([...tags, tag]);
    }

    function loadAvailableTags() {
        setIsLoadingTags(true);
        getAvailableTags()
            .then(async (res) => {
                if (!res.ok) return;
                const data = await res.json();
                if (Array.isArray(data.tags)) setAvailableTags(data.tags);
            })
            .finally(() => setIsLoadingTags(false));
    }

    const addableTags = availableTags.filter((tag) => !tags.includes(tag));

    return (
        <div className="flex flex-col gap-3">
            <h2 className="text-xs font-semibold tracking-widest text-grey uppercase">Interests</h2>

            <ul className="flex max-w-xl flex-wrap gap-2.5">
                {tags.length < MAX_TAGS && (
                    <li>
                        <Menu.Root onOpenChange={(open) => open && loadAvailableTags()}>
                            <Menu.Trigger
                                aria-label="Add interest"
                                disabled={isSaving}
                                className="flex h-9 cursor-pointer items-center justify-center rounded-full bg-grey/10 px-4 text-ink/70 transition hover:bg-grey/20 disabled:cursor-not-allowed"
                            >
                                <Plus className="h-4 w-4" />
                            </Menu.Trigger>
                            <Menu.Portal>
                                <Menu.Positioner side="bottom" align="start" sideOffset={8}>
                                    <Menu.Popup className="max-h-64 min-w-[180px] overflow-y-auto rounded-2xl bg-white p-1.5 shadow-xl shadow-ink/20 outline-none">
                                        {isLoadingTags && (
                                            <div className="flex items-center justify-center p-3">
                                                <Loader2 className="h-4 w-4 animate-spin text-matcha" />
                                            </div>
                                        )}
                                        {!isLoadingTags && addableTags.length === 0 && (
                                            <p className="px-3.5 py-2.5 text-sm text-ink/50">No more interests to add.</p>
                                        )}
                                        {addableTags.map((tag) => (
                                            <Menu.Item
                                                key={tag}
                                                closeOnClick={false}
                                                onClick={() => addTag(tag)}
                                                className="cursor-pointer rounded-xl px-3.5 py-2.5 text-sm font-medium text-ink outline-none transition data-[highlighted]:bg-grey/10"
                                            >
                                                {tag}
                                            </Menu.Item>
                                        ))}
                                    </Menu.Popup>
                                </Menu.Positioner>
                            </Menu.Portal>
                        </Menu.Root>
                    </li>
                )}

                {tags.map((tag) => (
                    <li key={tag}>
                        <button
                            type="button"
                            onClick={() => removeTag(tag)}
                            disabled={isSaving}
                            aria-label={`Remove ${tag}`}
                            className="flex h-9 cursor-pointer items-center gap-1.5 rounded-full bg-matcha px-4 text-sm font-medium text-matcha-dark transition hover:bg-matcha/80 disabled:cursor-not-allowed"
                        >
                            {tag}
                            <X className="h-3.5 w-3.5" />
                        </button>
                    </li>
                ))}
            </ul>
        </div>
    );
}
