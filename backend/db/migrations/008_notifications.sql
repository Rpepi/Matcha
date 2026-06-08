CREATE TABLE notifications (
    id           SERIAL PRIMARY KEY,
    user_id      INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    from_user_id INTEGER REFERENCES users(id) ON DELETE CASCADE,
    type         VARCHAR(20) NOT NULL,
    -- types: 'like', 'visit', 'message', 'match', 'unlike'
    seen         BOOLEAN DEFAULT false,
    created_at   TIMESTAMP DEFAULT NOW()
);

-- Speed up "my unread notifications" (badge in header)
CREATE INDEX idx_notifications_unread ON notifications(user_id, seen) WHERE seen = false;