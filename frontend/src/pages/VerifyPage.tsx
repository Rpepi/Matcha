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
        <>

        <div className="message-container">
            {info && <p className="msg-success">{info}</p>}
            {error && <p className="msg-error">{error}</p>}
            {!info && !error && <p className="msg-loading">Verification in progress...</p>}
        </div>
        </>
    )
}
