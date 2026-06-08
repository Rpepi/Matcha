CREATE TABLE users (
    -- Registration (IV.1)
    id              SERIAL PRIMARY KEY,
    username        VARCHAR(50) UNIQUE NOT NULL,
    email           VARCHAR(100) UNIQUE NOT NULL,
    first_name      VARCHAR(50) NOT NULL,
    last_name       VARCHAR(50) NOT NULL,
    password_hash   TEXT NOT NULL,
    age             INT NOT NULL,
    verified        BOOLEAN DEFAULT false,

    -- Profile (IV.2)
    gender          VARCHAR(20),
    orientation     VARCHAR(20) DEFAULT 'straight',
    bio             TEXT,
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
