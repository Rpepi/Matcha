CREATE TABLE visits (
    id          SERIAL PRIMARY KEY,
    visitor_id  INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    visited_id  INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    created_at  TIMESTAMP DEFAULT NOW(),

    CHECK (visitor_id != visited_id),
    UNIQUE (visitor_id, visited_id)
);

-- Speed up "who visited my profile" sorted by date
CREATE INDEX idx_visits_visited_id ON visits(visited_id, created_at DESC);