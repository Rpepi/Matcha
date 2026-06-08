CREATE TABLE likes (
    id          SERIAL PRIMARY KEY,
    liker_id    INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    liked_id    INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    created_at  TIMESTAMP DEFAULT NOW(),

    -- A user can only like another once
    UNIQUE (liker_id, liked_id),

    -- Cannot like yourself
    CHECK (liker_id != liked_id)
);

-- Speed up "who liked me" and "is it a match"
CREATE INDEX idx_likes_liked_id ON likes(liked_id);