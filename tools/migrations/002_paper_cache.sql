-- Migration 002: paper_cache
-- One row per (paper_id, expertise_level) pair.
-- Bibliography annotation cached here after first Haiku generation.
-- Embedding stored for pgvector similarity search.

CREATE EXTENSION IF NOT EXISTS vector;

CREATE TABLE IF NOT EXISTS paper_cache (
    paper_id        TEXT            NOT NULL,
    expertise_level TEXT            NOT NULL,   -- novice | intermediate | expert
    annotation      TEXT            NOT NULL,   -- cached bibliography annotation
    s2_tldr         TEXT,                       -- Semantic Scholar TL;DR (from Paper model)
    abstract        TEXT,                       -- full abstract at time of caching
    title           TEXT,
    embedding       VECTOR(1536),               -- OpenAI text-embedding-3-small
    model_used      TEXT,                       -- model that generated the annotation
    cached_at       TIMESTAMPTZ     NOT NULL DEFAULT now(),
    PRIMARY KEY (paper_id, expertise_level)
);

-- HNSW index for fast cosine similarity search
CREATE INDEX IF NOT EXISTS paper_cache_embedding
    ON paper_cache USING hnsw (embedding vector_cosine_ops);
