-- Migration 004: episodes status table
-- Tracks job lifecycle for API-triggered episode generation.
-- status: queued → running → done | failed

CREATE TABLE IF NOT EXISTS episodes (
    episode_id      TEXT        PRIMARY KEY,
    status          TEXT        NOT NULL DEFAULT 'queued',
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    completed_at    TIMESTAMPTZ,
    error           TEXT,
    manifest        JSONB
);

CREATE INDEX IF NOT EXISTS episodes_status     ON episodes (status);
CREATE INDEX IF NOT EXISTS episodes_created_at ON episodes (created_at);
