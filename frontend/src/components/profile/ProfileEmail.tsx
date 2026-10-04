export default function ProfileEmail({ email }: { email: string }) {
    return (
        <div className="flex flex-col gap-3">
            <h2 className="text-xs font-semibold tracking-widest text-grey uppercase">Email</h2>
            <p className="text-ink">{email}</p>
        </div>
    );
}
