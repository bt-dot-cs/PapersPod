-- Migration 005: user_id on episodes
-- Scopes episode list to the authenticated user who created it.

ALTER TABLE episodes ADD COLUMN IF NOT EXISTS user_id TEXT;

CREATE INDEX IF NOT EXISTS episodes_user_id ON episodes (user_id);
