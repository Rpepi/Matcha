CREATE TABLE blocks (
    id          SERIAL PRIMARY KEY,
    blocker_id  INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    blocked_id  INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    created_at  TIMESTAMP DEFAULT NOW(),

    UNIQUE (blocker_id, blocked_id),
    CHECK (blocker_id != blocked_id)
);

-- Speed up "is this user blocked" (checked on every browse/search query)
CREATE INDEX idx_blocks_blocker ON blocks(blocker_id);
CREATE INDEX idx_blocks_blocked ON blocks(blocked_id);

CREATE TABLE reports (
    id          SERIAL PRIMARY KEY,
    reporter_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    reported_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    reason      TEXT,
    created_at  TIMESTAMP DEFAULT NOW(),

    UNIQUE (reporter_id, reported_id),
    CHECK (reporter_id != reported_id)
);