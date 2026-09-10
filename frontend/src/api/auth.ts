export async function login(email: string, password: string): Promise<Response> {
    const response = await fetch('/api/auth/login', {
        method: 'POST',
        headers: {'Content-Type' : 'application/json'},
        credentials: 'include',
        body: JSON.stringify({ email, password}),
    })
    return response
}

export async function register(
    password: string,
    email: string,
    first_name: string,
    last_name: string,
): Promise<Response>
{
    const response = await fetch('/api/auth/register', {
        method: 'POST',
        headers: {'Content-Type' : 'application/json'},
        credentials: 'include',
        body: JSON.stringify({ password, email, first_name, last_name }),
    })
    return response
}
