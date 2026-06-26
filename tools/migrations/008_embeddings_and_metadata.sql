-- Migration 008: pgvector episode embeddings + metadata promotion

-- Requires pgvector extension (available on Neon)
CREATE EXTENSION IF NOT EXISTS vector;

-- Dual embeddings: target = 'paper_content' | 'episode_content'
-- paper_content  → topic + paper titles + abstracts (deterministic, rebuilt from Neon)
-- episode_content → script dialogue turns concatenated, speaker labels stripped (from R2)
CREATE TABLE IF NOT EXISTS episode_embeddings (
    episode_id      TEXT        NOT NULL REFERENCES episodes(episode_id),
    target          TEXT        NOT NULL,   -- 'paper_content' | 'episode_content'
    embedding       vector(1536) NOT NULL,
    embedding_model TEXT        NOT NULL,   -- e.g. 'text-embedding-3-small'
    embedded_at     TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (episode_id, target)
);

-- HNSW index for approximate nearest-neighbor search (cosine distance)
CREATE INDEX IF NOT EXISTS episode_embeddings_hnsw
    ON episode_embeddings
    USING hnsw (embedding vector_cosine_ops);

-- Promote metadata from manifest JSONB to indexed first-class columns
ALTER TABLE episodes
    ADD COLUMN IF NOT EXISTS expertise_level TEXT,
    ADD COLUMN IF NOT EXISTS disciplines     TEXT[],
    ADD COLUMN IF NOT EXISTS curation_level TEXT;

CREATE INDEX IF NOT EXISTS episodes_expertise_level ON episodes (expertise_level);
CREATE INDEX IF NOT EXISTS episodes_curation_level  ON episodes (curation_level);
CREATE INDEX IF NOT EXISTS episodes_disciplines     ON episodes USING GIN (disciplines);
