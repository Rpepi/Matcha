CREATE TABLE users (
    -- Registration (IV.1)
    id              SERIAL PRIMARY KEY,
    email           VARCHAR(100) UNIQUE NOT NULL,
    first_name      VARCHAR(50) NOT NULL,
    last_name       VARCHAR(50) NOT NULL,
    password_hash   TEXT NOT NULL,
    verified        BOOLEAN DEFAULT false,

    -- A new address waits here until its confirmation link is clicked; `email` (the
    -- one used to log in and to recover the account) never changes before that.
    -- Deliberately NOT unique: the address is typed by the user, who need not own it,
    -- so a unique index would let anyone squat an address by "waiting" for it. Several
    -- accounts may wait for the same one: the first to click its link gets it (`email`
    -- is unique, the others get a 409 when they click).
    pending_email   VARCHAR(100),
    -- 'email' for accounts made with a password, 'google' for those made by Google
    -- sign-in: only the former can change their email (Google finds the account by it).
    auth_provider   VARCHAR(20) NOT NULL DEFAULT 'email' CHECK (auth_provider IN ('email', 'google')),
    

    -- Profile (IV.2)
    gender          VARCHAR(20),
    orientation     VARCHAR(20) DEFAULT 'bi',
    bio             TEXT DEFAULT NULL,
    birth_date      DATE,
    fame_rating     INTEGER DEFAULT 0,

    -- Geolocation (IV.2)
    latitude        FLOAT,
    longitude       FLOAT,
    city            VARCHAR(100),

    -- Online status (IV.5)
    is_online       BOOLEAN DEFAULT false,
    last_seen       TIMESTAMP,

    -- Meta
    profile_complete BOOLEAN DEFAULT false,
    created_at      TIMESTAMP DEFAULT NOW()
);
