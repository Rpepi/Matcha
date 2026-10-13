/** `username` may also be the account's email address: the API accepts either. */
export async function login(username: string, password: string): Promise<Response> {
    const response = await fetch('/api/auth/login', {
        method: 'POST',
        headers: {'Content-Type' : 'application/json'},
        credentials: 'include',
        body: JSON.stringify({ username, password }),
    })
    return response
}

export async function logout(): Promise<Response> {
    const response = await fetch('/api/auth/logout', {
        method: 'POST',
        credentials: 'include',
    })
    return response
}

export async function register(
    password: string,
    email: string,
    username: string,
    first_name: string,
    last_name: string,
): Promise<Response>
{
    const response = await fetch('/api/auth/register', {
        method: 'POST',
        headers: {'Content-Type' : 'application/json'},
        credentials: 'include',
        body: JSON.stringify({ password, email, username, first_name, last_name }),
    })
    return response
}

export async function forgotPassword(email: string): Promise<Response> {
    const response = await fetch('/api/auth/forgot-password', {
        method: 'POST',
        headers: {'Content-Type' : 'application/json'},
        credentials: 'include',
        body: JSON.stringify({ email }),
    })
    return response
}

export async function resetPassword(token: string, new_password: string): Promise<Response> {
    const response = await fetch('/api/auth/reset-password', {
        method: 'POST',
        headers: {'Content-Type' : 'application/json'},
        credentials: 'include',
        body: JSON.stringify({ token, new_password }),
    })
    return response
}
