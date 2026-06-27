-- Migration 010: key pool + BYOK + LLM call telemetry

-- User-supplied (BYOK) API keys — one per provider per user
CREATE TABLE user_api_keys (
  id            BIGSERIAL PRIMARY KEY,
  user_id       TEXT NOT NULL,
  provider      TEXT NOT NULL,  -- 'anthropic' | 'openai' | 'gemini'
  encrypted_key TEXT NOT NULL,
  key_hint      TEXT NOT NULL,  -- e.g. "sk-...f3k2"
  created_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
  last_used_at  TIMESTAMPTZ,
  active        BOOLEAN NOT NULL DEFAULT true,
  UNIQUE (user_id, provider)
);

-- Deterministic A/B provider assignment per user per pipeline stage
CREATE TABLE user_provider_assignments (
  user_id     TEXT NOT NULL,
  stage       TEXT NOT NULL,
  provider    TEXT NOT NULL,
  assigned_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  PRIMARY KEY (user_id, stage)
);

-- Per-call LLM telemetry
CREATE TABLE llm_calls (
  id            BIGSERIAL PRIMARY KEY,
  episode_id    TEXT,
  user_id       TEXT,
  stage         TEXT NOT NULL,
  provider      TEXT NOT NULL,
  model         TEXT NOT NULL,
  key_source    TEXT NOT NULL,  -- 'byok' | 'platform'
  key_index     INT,            -- platform pool slot index (null for byok)
  input_tokens  INT,
  output_tokens INT,
  latency_ms    INT,
  created_at    TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_llm_calls_episode ON llm_calls (episode_id);
CREATE INDEX idx_llm_calls_user    ON llm_calls (user_id, created_at DESC);
