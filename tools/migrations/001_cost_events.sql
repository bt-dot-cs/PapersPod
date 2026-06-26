-- Migration 001: cost_events
-- One row per completed episode run.
-- Manifest JSON in object storage is the immutable audit record; this table is queryable.

CREATE TABLE IF NOT EXISTS cost_events (
    id                      SERIAL          PRIMARY KEY,
    episode_id              TEXT            NOT NULL UNIQUE,
    user_id                 TEXT,
    created_at              TIMESTAMPTZ     NOT NULL,

    topic                   TEXT,
    source                  TEXT,
    expertise_level         TEXT,
    max_papers              INTEGER,
    anchor_paper            TEXT,

    tokens_input            INTEGER         NOT NULL DEFAULT 0,
    tokens_output           INTEGER         NOT NULL DEFAULT 0,

    cost_claude_input       NUMERIC(10, 6)  NOT NULL DEFAULT 0,
    cost_claude_output      NUMERIC(10, 6)  NOT NULL DEFAULT 0,
    cost_claude             NUMERIC(10, 6)  NOT NULL DEFAULT 0,
    cost_tts                NUMERIC(10, 6)  NOT NULL DEFAULT 0,
    cost_total              NUMERIC(10, 6)  NOT NULL DEFAULT 0,

    tts_provider_requested  TEXT,
    tts_provider_used       TEXT,
    tts_fallback_occurred   BOOLEAN         DEFAULT FALSE,
    tts_characters          INTEGER         DEFAULT 0,

    runtime_seconds         NUMERIC(10, 2),
    trace_reasoning         BOOLEAN         DEFAULT FALSE,
    commercial_mode         BOOLEAN         DEFAULT FALSE,
    warnings                JSONB           DEFAULT '[]'
);

CREATE INDEX IF NOT EXISTS cost_events_created_at  ON cost_events (created_at);
CREATE INDEX IF NOT EXISTS cost_events_user_id     ON cost_events (user_id);
CREATE INDEX IF NOT EXISTS cost_events_source      ON cost_events (source);
CREATE INDEX IF NOT EXISTS cost_events_tts_used    ON cost_events (tts_provider_used);
