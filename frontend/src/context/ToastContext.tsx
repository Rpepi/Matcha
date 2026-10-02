import { createContext, useCallback, useContext, useRef, useState, type ReactNode } from "react";
import Toast from "../components/Toast";

export type ToastVariant = "error" | "notice";

export interface ToastState {
    id: number;
    message: string;
    variant: ToastVariant;
}

interface ToastContextValue {
    showError: (message: string) => void;
    showNotice: (message: string) => void;
}

const ToastContext = createContext<ToastContextValue | undefined>(undefined);

const AUTO_DISMISS_MS = 5000;

export function ToastProvider({ children }: { children: ReactNode }) {
    const [toast, setToast] = useState<ToastState | null>(null);
    const timeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null);
    const nextId = useRef(0);

    const dismiss = useCallback(() => {
        if (timeoutRef.current) clearTimeout(timeoutRef.current);
        setToast(null);
    }, []);

    const show = useCallback((message: string, variant: ToastVariant) => {
        if (timeoutRef.current) clearTimeout(timeoutRef.current);
        const id = ++nextId.current;
        setToast({ id, message, variant });
        timeoutRef.current = setTimeout(() => {
            setToast((current) => (current?.id === id ? null : current));
        }, AUTO_DISMISS_MS);
    }, []);

    const showError = useCallback((message: string) => show(message, "error"), [show]);
    const showNotice = useCallback((message: string) => show(message, "notice"), [show]);

    return (
        <ToastContext.Provider value={{ showError, showNotice }}>
            {children}
            <Toast toast={toast} onDismiss={dismiss} />
        </ToastContext.Provider>
    );
}

export function useToast(): ToastContextValue {
    const ctx = useContext(ToastContext);
    if (!ctx) throw new Error("useToast must be used within a ToastProvider");
    return ctx;
}
