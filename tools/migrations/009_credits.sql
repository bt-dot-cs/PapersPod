-- Migration 009: credit ledger (user_credits + credit_events)
-- Tracks per-user credit balance and full earn/spend history.

CREATE TABLE IF NOT EXISTS user_credits (
    user_id    TEXT PRIMARY KEY,
    balance    INTEGER NOT NULL DEFAULT 0 CHECK (balance >= 0),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS credit_events (
    id         BIGSERIAL PRIMARY KEY,
    user_id    TEXT NOT NULL,
    delta      INTEGER NOT NULL,          -- positive = earn, negative = spend
    event_type TEXT NOT NULL,             -- 'signup_bonus' | 'episode_generated' | 'refund' | 'feedback_bug' | 'feedback_improvement' | 'feedback_positive' | 'subscription_grant' | 'bundle_purchase' | 'episode_completed' | ...
    episode_id TEXT,
    metadata   JSONB,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS credit_events_user_created
    ON credit_events (user_id, created_at DESC);

CREATE INDEX IF NOT EXISTS credit_events_user_type_created
    ON credit_events (user_id, event_type, created_at DESC);
