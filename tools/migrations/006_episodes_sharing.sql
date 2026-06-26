-- Migration 006: episode sharing + script embeddings
-- Enables the community library (Step 10.5).

ALTER TABLE episodes ADD COLUMN IF NOT EXISTS shared        BOOLEAN     NOT NULL DEFAULT FALSE;
ALTER TABLE episodes ADD COLUMN IF NOT EXISTS shared_at     TIMESTAMPTZ;
ALTER TABLE episodes ADD COLUMN IF NOT EXISTS script_embedding VECTOR(1536);

-- Fast lookup for library queries (shared=TRUE is a small fraction of rows)
CREATE INDEX IF NOT EXISTS episodes_shared
    ON episodes (shared) WHERE shared = TRUE;

-- HNSW index for cosine similarity on script embeddings
CREATE INDEX IF NOT EXISTS episodes_script_emb
    ON episodes USING hnsw (script_embedding vector_cosine_ops)
    WHERE script_embedding IS NOT NULL;
