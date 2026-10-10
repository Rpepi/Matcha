import { Eye } from "lucide-react";
import { useProfileEntries } from "@/hooks/useProfileEntries";
import { getVisits, type Visit } from "@/api/profile";
import PeopleList from "./PeopleList";

export default function VisitorsList() {
    const { entries, isLoading, loadError, retry } = useProfileEntries<Visit>(getVisits);

    return (
        <PeopleList
            entries={entries}
            isLoading={isLoading}
            loadError={loadError}
            retry={retry}
            getPersonId={(visit) => visit.visitor_id}
            icon={<Eye className="h-7 w-7 text-ink" />}
            ariaLabel="Visitors"
            emptyTitle="No visitors yet"
            emptyDescription="People who view your profile will show up here."
            actionText="Viewed your profile"
            loadErrorText="Could not load visitors. Please try again."
        />
    );
}
