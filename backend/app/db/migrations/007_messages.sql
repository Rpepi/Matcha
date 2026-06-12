CREATE TABLE messages (
    id          SERIAL PRIMARY KEY,
    sender_id   INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    receiver_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    content     TEXT NOT NULL,
    seen        BOOLEAN DEFAULT false,
    created_at  TIMESTAMP DEFAULT NOW(),

    CHECK (sender_id != receiver_id)
);

-- Speed up loading a conversation between 2 users
CREATE INDEX idx_messages_conversation ON messages(
    LEAST(sender_id, receiver_id),
    GREATEST(sender_id, receiver_id),
    created_at
);

-- Speed up "unread messages for me"
CREATE INDEX idx_messages_unseen ON messages(receiver_id, seen) WHERE seen = false;