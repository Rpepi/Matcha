-- Username (IV.1): users register and log in with a unique username.
-- Existing accounts get one derived from their first name plus their id, which
-- is unique by construction (the id is the part that differs).
ALTER TABLE users ADD COLUMN username VARCHAR(30);

UPDATE users
SET username = COALESCE(NULLIF(left(lower(regexp_replace(first_name, '[^A-Za-z0-9]', '', 'g')), 20), ''), 'user') || id;

ALTER TABLE users ALTER COLUMN username SET NOT NULL;

-- Case-insensitive: "Alice" and "alice" are the same username.
CREATE UNIQUE INDEX users_username_lower_key ON users (lower(username));
