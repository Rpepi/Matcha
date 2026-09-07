import type {
    InputHTMLAttributes,
    SelectHTMLAttributes,
    ButtonHTMLAttributes,
    ReactNode,
} from "react"

const fieldClasses =
    "w-full rounded-xl border border-plum/15 bg-white px-4 py-2.5 text-plum placeholder:text-plum/40 outline-none transition focus:border-orchid focus:ring-2 focus:ring-orchid/30";

interface FieldProps extends InputHTMLAttributes<HTMLInputElement> {
    label?: string
}

export function Field({ label, id, className = "", ...props }: FieldProps) {
    return (
        <label htmlFor={id} className="block">
            <span className="mb-1.5 block text-sm font-medium text-plum/80">
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
            <span className="mb-1.5 block text-sm font-medium text-plum/80">
                {label}
            </span>
            <select id={id} className={`${fieldClasses} ${className}`} {...props}>
                {children}
            </select>
        </label>
    );
}

type GradientButtonProps = ButtonHTMLAttributes<HTMLButtonElement>

export function GradientButton({ children, className = "", ...props }: GradientButtonProps) {
    return (
        <button
            className={`w-full rounded-xl bg-gradient-to-r from-garnet to-orchid px-4 py-2.5 font-medium text-petal shadow-lg shadow-garnet/25 transition hover:brightness-110 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-orchid disabled:cursor-not-allowed disabled:opacity-60 ${className}`}
            {...props}
        >
            {children}
        </button>
    );
}

export function OrDivider({ label = "or" }: { label?: string }) {
    return (
        <div className="flex items-center gap-3 text-xs font-medium text-plum/40">
            <span className="h-px flex-1 bg-plum/10" />
            {label}
            <span className="h-px flex-1 bg-plum/10" />
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
        error: "bg-garnet/10 text-garnet border-garnet/20",
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
