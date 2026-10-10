import { useSearchParams } from "react-router-dom";
import { useRef, useState } from "react";
import { useEffect } from "react";


export default function VerifyPage() {
    const [info, setInfo] = useState('');
    const [error, setError] = useState('');
    const [searchParams] = useSearchParams();
    const token = searchParams.get("token");
    const hasRequested = useRef(false);


    useEffect( () => {
        const verify = async () => {
            if (hasRequested.current === false)
            {
                hasRequested.current = true
                try {
                    const response = await fetch(`/api/auth/verify?token=${token}`, {
                        method: 'GET',
                        headers: {'Content-Type' : 'application/json'}
                    });

                    if (response.ok)
                        setInfo("Email verified! you can close this page.");
                    else
                        setError("Error verifiyng email, Try again!");
                } catch {
                    setError("Could not verify your email. Please check your connection and try again.");
                }
            }
        };
        verify();
    }, [token]);

    return (
        <div className="flex min-h-dvh items-center justify-center p-6 text-center">
            {info && <p className="text-sm font-medium text-matcha-dark">{info}</p>}
            {error && <p className="text-sm font-medium text-pink">{error}</p>}
            {!info && !error && <p className="text-sm text-ink/60">Verification in progress...</p>}
        </div>
    )
}
