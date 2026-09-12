import type {
    InputHTMLAttributes,
    SelectHTMLAttributes,
    ButtonHTMLAttributes,
    ReactNode,
} from "react"

const fieldClasses =
    "w-full rounded-xl border border-grey/30 bg-transparent px-4 py-2.5 text-ink placeholder:text-ink/40 outline-none transition focus:ring-2 focus:ring-grey/30";

interface FieldProps extends InputHTMLAttributes<HTMLInputElement> {
    label?: string
}

export function Field({ label, id, className = "", ...props }: FieldProps) {
    return (
        <label htmlFor={id} className="block">
            <span className="mb-1.5 block text-sm font-medium text-ink">
                {label}
            </span>
            <input id={id} className={`${fieldClasses} ${className}`} {...props} />
        </label>
    );
}

interface SelectFieldProps extends SelectHTMLAttributes<HTMLSelectElement> {
    label?: string
}

export function SelectField({ label, id, className = "", children, ...props }: SelectFieldProps) {
    return (
        <label htmlFor={id} className="block">
            <span className="mb-1.5 block text-sm font-medium text-ink/80">
                {label}
            </span>
            <select id={id} className={`${fieldClasses} ${className}`} {...props}>
                {children}
            </select>
        </label>
    );
}

type ButtonProps = ButtonHTMLAttributes<HTMLButtonElement>

export function Button({ children, className = "", ...props }: ButtonProps) {
    return (
        <button
            className={`group w-full cursor-pointer rounded-xl bg-matcha px-4 py-2.5 font-medium text-ink transition focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-matcha disabled:cursor-not-allowed disabled:opacity-60 ${className}`}
            {...props}
        >
            <span className="inline-block transition-transform duration-300 ease-[cubic-bezier(0.34,1.56,0.64,1)] group-hover:-translate-y-1 group-active:translate-y-1 group-active:duration-150 group-active:ease-out">
                {children}
            </span>
        </button>
    );
}

export function OrDivider({ label = "or" }: { label?: string }) {
    return (
        <div className="flex items-center gap-3 text-xs font-medium text-ink/40">
            <span className="h-px flex-1 bg-ink/10" />
            {label}
            <span className="h-px flex-1 bg-ink/10" />
        </div>
    );
}

interface FormNoticeProps {
    tone?: "error" | "info"
    children?: ReactNode
}

export function FormNotice({ tone = "error", children }: FormNoticeProps) {
    if (!children) return null;
    const tones = {
        error: "bg-pink/10 text-pink border-pink/20",
        info: "bg-orchid/10 text-orchid border-orchid/20",
    };
    return (
        <p
            role={tone === "error" ? "alert" : "status"}
            className={`rounded-xl border px-3.5 py-2.5 text-sm ${tones[tone]}`}
        >
            {children}
        </p>
    );
}
