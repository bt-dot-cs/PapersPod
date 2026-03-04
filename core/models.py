from datetime import date, datetime
from enum import Enum
from pathlib import Path
from typing import Literal, Optional

from pydantic import BaseModel, field_validator


class ExpertiseLevel(str, Enum):
    novice = "novice"          # Foundational papers, define jargon, use analogies
    intermediate = "intermediate"  # Methodology focus, assumes basics, surfaces debates
    expert = "expert"          # Frontier papers, novel contributions, open questions


class ExpertiseProfile(BaseModel):
    discipline: str            # e.g., "machine learning"
    level: ExpertiseLevel


class UserProfile(BaseModel):
    expertise: list[ExpertiseProfile]
    default_level: ExpertiseLevel = ExpertiseLevel.intermediate


class QueryParameters(BaseModel):
    topic: str
    disciplines: list[str]
    cross_disciplinary: bool = False
    focus_mode: Literal["depth", "breadth"] = "breadth"
    publication_date_range: tuple[date, date]
    study_data_period: Optional[tuple[date, date]] = None
    max_papers: int = 10
    include_preprints: bool = True
    user_profile: Optional[UserProfile] = None
    source: Literal["auto", "arxiv", "openalex"] = "auto"

    @field_validator("publication_date_range")
    @classmethod
    def validate_date_range(cls, v: tuple[date, date]) -> tuple[date, date]:
        start, end = v
        if start > end:
            raise ValueError("publication_date_range start must be before end")
        return v

    @field_validator("max_papers")
    @classmethod
    def validate_max_papers(cls, v: int) -> int:
        if v < 1:
            raise ValueError("max_papers must be at least 1")
        return v


class Paper(BaseModel):
    arxiv_id: str                              # Canonical deduplication key
    title: str
    authors: list[str]
    abstract: str
    published_date: date
    study_period_start: Optional[date] = None  # Temporal scope of referenced data
    study_period_end: Optional[date] = None
    pdf_url: Optional[str] = None
    # Source metadata
    openalex_id: Optional[str] = None          # OpenAlex work ID (e.g. W2741809807)
    # Semantic Scholar enrichment
    citation_count: Optional[int] = None
    citation_velocity: Optional[float] = None  # Citations per year
    s2_tldr: Optional[str] = None
    # Graph state
    first_seen_date: Optional[date] = None
    # User ratings (populated post-episode)
    interest_score: Optional[int] = None       # 1–5
    depth_score: Optional[int] = None          # 1–5
    flagged_for_reading: bool = False


class DialogueTurn(BaseModel):
    host: Literal["A", "B"]
    text: str
    audio_segment_path: Optional[Path] = None  # Set by VoiceAgent


class PodcastScript(BaseModel):
    episode_id: str
    title: str
    turns: list[DialogueTurn]
    paper_ids: list[str]                       # arXiv IDs discussed


class Episode(BaseModel):
    episode_id: str
    query: QueryParameters
    papers: list[Paper]
    bibliography_path: Optional[Path] = None
    script_path: Optional[Path] = None
    audio_path: Optional[Path] = None
    graph_snapshot_path: Optional[Path] = None
    created_at: datetime


class PaperRating(BaseModel):
    paper_id: str
    episode_id: str
    interest_score: int    # 1–5
    depth_score: int       # 1–5
    flag_for_reading: bool = False
    notes: Optional[str] = None

    @field_validator("interest_score", "depth_score")
    @classmethod
    def validate_score(cls, v: int) -> int:
        if not 1 <= v <= 5:
            raise ValueError("Score must be between 1 and 5")
        return v


class ReadingQueueItem(BaseModel):
    paper_id: str
    title: str
    added_date: date
    priority: int = 3      # 1–5, higher = more urgent
    status: Literal["queued", "reading", "done"] = "queued"

    @field_validator("priority")
    @classmethod
    def validate_priority(cls, v: int) -> int:
        if not 1 <= v <= 5:
            raise ValueError("Priority must be between 1 and 5")
        return v
