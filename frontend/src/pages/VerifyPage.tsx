import { useSearchParams } from "react-router-dom";
import { useState } from "react";
import { useEffect } from "react";


export default function VerifyPage() {
    const [info, setInfo] = useState('');
    const [error, setError] = useState('');
    const [searchParams] = useSearchParams();
    const token = searchParams.get("token");

    useEffect( () => {
        const verify = async () => {
            const response = await fetch(`/api/auth/verify?token=${token}`, {
                method: 'GET',
                headers: {'Content-Type' : 'application/json'}
        });
        if (response.ok)
            setInfo("Email verified! you can close this page.");
        else
            setError("Error verifiyng email, Try again!");
    };
    verify();
    }, []);

    return (
        <div className="flex min-h-dvh items-center justify-center p-6 text-center">
            {info && <p className="text-sm font-medium text-matcha-dark">{info}</p>}
            {error && <p className="text-sm font-medium text-pink">{error}</p>}
            {!info && !error && <p className="text-sm text-ink/60">Verification in progress...</p>}
        </div>
    )
}
