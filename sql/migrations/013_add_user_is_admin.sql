-- sql/migrations/013_add_user_is_admin.sql
--
-- Add is_admin to users so the /admin/* web pages can be gated behind an
-- admin-only session. No existing user is granted admin by this migration;
-- grants are done via backend/scripts/grant_admin.py.

ALTER TABLE users
    ADD COLUMN IF NOT EXISTS is_admin BOOLEAN NOT NULL DEFAULT false;

COMMENT ON COLUMN users.is_admin IS
    'True if user may access /admin web pages. Granted via backend/scripts/grant_admin.py.';

CREATE INDEX IF NOT EXISTS idx_users_is_admin
    ON users(is_admin)
    WHERE is_admin = true;

select * from users
