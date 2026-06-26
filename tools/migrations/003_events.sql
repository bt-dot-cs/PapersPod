-- Migration 003: play_events + doi_referral_events
-- Append-only event tables. Never update or delete rows — these are pre-financial records.

CREATE TABLE IF NOT EXISTS play_events (
    id              BIGSERIAL       PRIMARY KEY,
    episode_id      TEXT            NOT NULL,
    user_id         TEXT,                       -- NULL for anonymous listeners
    session_id      TEXT,                       -- anonymous session token
    event_type      TEXT            NOT NULL,   -- play | pause | complete | seek
    completion_pct  NUMERIC(5, 2),              -- 0.00–100.00
    timestamp       TIMESTAMPTZ     NOT NULL DEFAULT now(),
    ip_hash         TEXT                        -- SHA-256 of IP, for dedup without PII
);

CREATE INDEX IF NOT EXISTS play_events_episode_id  ON play_events (episode_id);
CREATE INDEX IF NOT EXISTS play_events_user_id     ON play_events (user_id);
CREATE INDEX IF NOT EXISTS play_events_timestamp   ON play_events (timestamp);

CREATE TABLE IF NOT EXISTS doi_referral_events (
    id              BIGSERIAL       PRIMARY KEY,
    doi             TEXT            NOT NULL,
    episode_id      TEXT,
    user_id         TEXT,
    session_id      TEXT,
    timestamp       TIMESTAMPTZ     NOT NULL DEFAULT now(),
    referrer        TEXT
);

CREATE INDEX IF NOT EXISTS doi_referral_events_doi        ON doi_referral_events (doi);
CREATE INDEX IF NOT EXISTS doi_referral_events_episode_id ON doi_referral_events (episode_id);
CREATE INDEX IF NOT EXISTS doi_referral_events_timestamp  ON doi_referral_events (timestamp);
