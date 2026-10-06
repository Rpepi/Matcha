import { Menu } from "@base-ui/react/menu";
import { Loader2, Plus, X } from "lucide-react";
import { useProfileTags, MAX_TAGS } from "@/hooks/useProfileTags";

export default function ProfileTags({ tags }: { tags: string[] }) {
    const { isSaving, isLoadingTags, addableTags, loadAvailableTags, addTag, removeTag } = useProfileTags(tags);

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
