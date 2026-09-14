CREATE TABLE photos (
    id          SERIAL PRIMARY KEY,
    user_id     INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    path        TEXT NOT NULL,
    is_profile  BOOLEAN DEFAULT false,
    position    SMALLINT NOT NULL CHECK (position >= 1 AND position <= 5), -- Max 5 photos
    created_at  TIMESTAMP DEFAULT NOW()
);

-- Only one photo per slot per user
CREATE UNIQUE INDEX idx_photos_user_position ON photos(user_id, position);
