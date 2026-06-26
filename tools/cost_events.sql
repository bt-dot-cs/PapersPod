-- PapersPod cost_events table
--
-- One row per completed episode run. The manifest JSON in object storage is the
-- immutable audit record; this table is the queryable aggregate layer.
--
-- Migration path: when the server-side pipeline lands, the orchestrator's
-- manifest-write step becomes a dual-write — same data, also INSERT here.
-- tools/cost_summary.py reads manifests today; at production it queries this table.

CREATE TABLE IF NOT EXISTS cost_events (
    id                      SERIAL          PRIMARY KEY,
    episode_id              TEXT            NOT NULL UNIQUE,
    user_id                 TEXT,                               -- NULL in CLI / personal mode
    created_at              TIMESTAMPTZ     NOT NULL,

    -- Run parameters
    topic                   TEXT,
    source                  TEXT,
    expertise_level         TEXT,
    max_papers              INTEGER,
    anchor_paper            TEXT,

    -- Tokens
    tokens_input            INTEGER         NOT NULL DEFAULT 0,
    tokens_output           INTEGER         NOT NULL DEFAULT 0,

    -- Costs (USD, 6 decimal places for micro-payment precision)
    cost_claude_input       NUMERIC(10, 6)  NOT NULL DEFAULT 0,
    cost_claude_output      NUMERIC(10, 6)  NOT NULL DEFAULT 0,
    cost_claude             NUMERIC(10, 6)  NOT NULL DEFAULT 0,
    cost_tts                NUMERIC(10, 6)  NOT NULL DEFAULT 0,
    cost_total              NUMERIC(10, 6)  NOT NULL DEFAULT 0,

    -- TTS
    tts_provider_requested  TEXT,
    tts_provider_used       TEXT,
    tts_fallback_occurred   BOOLEAN         DEFAULT FALSE,
    tts_characters          INTEGER         DEFAULT 0,

    -- Runtime
    runtime_seconds         NUMERIC(10, 2),

    -- Flags
    trace_reasoning         BOOLEAN         DEFAULT FALSE,
    commercial_mode         BOOLEAN         DEFAULT FALSE,

    -- Warnings (preserved from manifest)
    warnings                JSONB           DEFAULT '[]'
);

-- Common query patterns
CREATE INDEX IF NOT EXISTS cost_events_created_at  ON cost_events (created_at);
CREATE INDEX IF NOT EXISTS cost_events_user_id     ON cost_events (user_id);
CREATE INDEX IF NOT EXISTS cost_events_source      ON cost_events (source);
CREATE INDEX IF NOT EXISTS cost_events_tts_used    ON cost_events (tts_provider_used);
