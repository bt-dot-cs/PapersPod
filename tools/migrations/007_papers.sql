-- Migration 007: paper metadata, episode↔paper linking, click-through tracking

CREATE TABLE IF NOT EXISTS papers (
    arxiv_id         TEXT PRIMARY KEY,
    doi              TEXT,
    title            TEXT NOT NULL,
    authors          JSONB NOT NULL DEFAULT '[]',
    published_date   DATE,
    abstract_snippet TEXT
);

CREATE TABLE IF NOT EXISTS episode_papers (
    episode_id    TEXT NOT NULL REFERENCES episodes(episode_id),
    arxiv_id      TEXT NOT NULL REFERENCES papers(arxiv_id),
    annotation    TEXT,
    display_order INT  NOT NULL DEFAULT 0,
    PRIMARY KEY (episode_id, arxiv_id)
);

CREATE INDEX IF NOT EXISTS episode_papers_episode_id ON episode_papers(episode_id);

CREATE TABLE IF NOT EXISTS paper_clicks (
    id          BIGSERIAL PRIMARY KEY,
    episode_id  TEXT REFERENCES episodes(episode_id),
    arxiv_id    TEXT REFERENCES papers(arxiv_id),
    user_id     TEXT,
    session_id  TEXT,
    clicked_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS paper_clicks_episode_id ON paper_clicks(episode_id);
CREATE INDEX IF NOT EXISTS paper_clicks_arxiv_id   ON paper_clicks(arxiv_id);
