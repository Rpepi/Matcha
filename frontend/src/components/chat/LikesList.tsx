import { Heart } from "lucide-react";
import { useProfileEntries } from "@/hooks/useProfileEntries";
import { getLikes, type Like } from "@/api/profile";
import PeopleList from "./PeopleList";

export default function LikesList() {
    const { entries, isLoading, loadError, retry } = useProfileEntries<Like>(getLikes);

    return (
        <PeopleList
            entries={entries}
            isLoading={isLoading}
            loadError={loadError}
            retry={retry}
            getPersonId={(like) => like.liker_id}
            icon={<Heart className="h-7 w-7 text-ink" />}
            ariaLabel="Likes"
            emptyTitle="No likes yet"
            emptyDescription="People who like your profile will show up here."
            actionText="Liked your profile"
            loadErrorText="Could not load likes. Please try again."
        />
    );
}
