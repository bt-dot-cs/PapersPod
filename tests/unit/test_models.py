from datetime import date, datetime

import pytest
from pydantic import ValidationError

from core.models import (
    DialogueTurn,
    Episode,
    ExpertiseLevel,
    ExpertiseProfile,
    Paper,
    PaperRating,
    PodcastScript,
    QueryParameters,
    ReadingQueueItem,
    UserProfile,
)


# --- QueryParameters ---

def test_query_parameters_valid():
    qp = QueryParameters(
        topic="transformer architectures",
        disciplines=["machine learning"],
        publication_date_range=(date(2022, 1, 1), date(2026, 1, 1)),
    )
    assert qp.focus_mode == "breadth"
    assert qp.max_papers == 10
    assert qp.include_preprints is True
    assert qp.cross_disciplinary is False
    assert qp.study_data_period is None


def test_query_parameters_invalid_date_range():
    with pytest.raises(ValidationError, match="start must be before end"):
        QueryParameters(
            topic="test",
            disciplines=["ml"],
            publication_date_range=(date(2026, 1, 1), date(2022, 1, 1)),
        )


def test_query_parameters_invalid_max_papers():
    with pytest.raises(ValidationError, match="at least 1"):
        QueryParameters(
            topic="test",
            disciplines=["ml"],
            publication_date_range=(date(2022, 1, 1), date(2026, 1, 1)),
            max_papers=0,
        )


def test_query_parameters_with_user_profile():
    profile = UserProfile(
        expertise=[ExpertiseProfile(discipline="machine learning", level=ExpertiseLevel.expert)],
        default_level=ExpertiseLevel.intermediate,
    )
    qp = QueryParameters(
        topic="test",
        disciplines=["machine learning"],
        publication_date_range=(date(2022, 1, 1), date(2026, 1, 1)),
        user_profile=profile,
    )
    assert qp.user_profile.default_level == ExpertiseLevel.intermediate


def test_query_parameters_same_start_end_date():
    # Same start and end should be valid
    qp = QueryParameters(
        topic="test",
        disciplines=["ml"],
        publication_date_range=(date(2024, 1, 1), date(2024, 1, 1)),
    )
    assert qp.publication_date_range[0] == qp.publication_date_range[1]


# --- ExpertiseLevel / ExpertiseProfile / UserProfile ---

def test_expertise_level_values():
    assert ExpertiseLevel.novice == "novice"
    assert ExpertiseLevel.intermediate == "intermediate"
    assert ExpertiseLevel.expert == "expert"


def test_expertise_profile():
    ep = ExpertiseProfile(discipline="neuroscience", level=ExpertiseLevel.novice)
    assert ep.discipline == "neuroscience"
    assert ep.level == ExpertiseLevel.novice


def test_user_profile_default_level():
    profile = UserProfile(expertise=[])
    assert profile.default_level == ExpertiseLevel.intermediate


def test_user_profile_multiple_disciplines():
    profile = UserProfile(
        expertise=[
            ExpertiseProfile(discipline="machine learning", level=ExpertiseLevel.expert),
            ExpertiseProfile(discipline="neuroscience", level=ExpertiseLevel.novice),
        ],
        default_level=ExpertiseLevel.intermediate,
    )
    assert len(profile.expertise) == 2


# --- Paper ---

def test_paper_required_fields():
    paper = Paper(
        arxiv_id="2301.12345",
        title="Attention Is All You Need",
        authors=["Vaswani, A.", "Shazeer, N."],
        abstract="We propose a new architecture...",
        published_date=date(2017, 6, 12),
    )
    assert paper.arxiv_id == "2301.12345"
    assert paper.citation_count is None
    assert paper.citation_velocity is None
    assert paper.s2_tldr is None
    assert paper.flagged_for_reading is False
    assert paper.first_seen_date is None


def test_paper_all_fields():
    paper = Paper(
        arxiv_id="2301.12345",
        title="Test Paper",
        authors=["Author A"],
        abstract="Abstract text",
        published_date=date(2023, 1, 15),
        citation_count=150,
        citation_velocity=30.0,
        s2_tldr="One sentence summary.",
        first_seen_date=date(2026, 3, 4),
        interest_score=4,
        depth_score=5,
        flagged_for_reading=True,
    )
    assert paper.citation_count == 150
    assert paper.flagged_for_reading is True


# --- PaperRating ---

def test_paper_rating_valid():
    rating = PaperRating(
        paper_id="2301.12345",
        episode_id="2026-03-04_transformers_ab12",
        interest_score=4,
        depth_score=5,
    )
    assert rating.flag_for_reading is False
    assert rating.notes is None


def test_paper_rating_score_too_high():
    with pytest.raises(ValidationError, match="between 1 and 5"):
        PaperRating(
            paper_id="2301.12345",
            episode_id="ep1",
            interest_score=6,
            depth_score=3,
        )


def test_paper_rating_score_too_low():
    with pytest.raises(ValidationError, match="between 1 and 5"):
        PaperRating(
            paper_id="2301.12345",
            episode_id="ep1",
            interest_score=1,
            depth_score=0,
        )


def test_paper_rating_with_notes():
    rating = PaperRating(
        paper_id="2301.12345",
        episode_id="ep1",
        interest_score=5,
        depth_score=5,
        flag_for_reading=True,
        notes="Great paper on attention mechanisms.",
    )
    assert rating.notes == "Great paper on attention mechanisms."
    assert rating.flag_for_reading is True


# --- ReadingQueueItem ---

def test_reading_queue_item_defaults():
    item = ReadingQueueItem(
        paper_id="2301.12345",
        title="Test Paper",
        added_date=date(2026, 3, 4),
    )
    assert item.priority == 3
    assert item.status == "queued"


def test_reading_queue_item_invalid_priority():
    with pytest.raises(ValidationError, match="between 1 and 5"):
        ReadingQueueItem(
            paper_id="2301.12345",
            title="Test",
            added_date=date(2026, 3, 4),
            priority=6,
        )


def test_reading_queue_item_status_values():
    for status in ("queued", "reading", "done"):
        item = ReadingQueueItem(
            paper_id="2301.12345",
            title="Test",
            added_date=date(2026, 3, 4),
            status=status,
        )
        assert item.status == status


# --- DialogueTurn ---

def test_dialogue_turn_host_a():
    turn = DialogueTurn(host="A", text="Hello, welcome to PapersPod!")
    assert turn.host == "A"
    assert turn.audio_segment_path is None


def test_dialogue_turn_host_b():
    turn = DialogueTurn(host="B", text="So what does this paper actually argue?")
    assert turn.host == "B"


def test_dialogue_turn_invalid_host():
    with pytest.raises(ValidationError):
        DialogueTurn(host="C", text="Invalid host")


# --- PodcastScript ---

def test_podcast_script():
    script = PodcastScript(
        episode_id="2026-03-04_transformers_ab12",
        title="Understanding Transformers",
        turns=[
            DialogueTurn(host="A", text="Let's talk about attention."),
            DialogueTurn(host="B", text="What is attention exactly?"),
        ],
        paper_ids=["2301.12345", "1706.03762"],
    )
    assert len(script.turns) == 2
    assert len(script.paper_ids) == 2


# --- Episode ---

def test_episode_model():
    qp = QueryParameters(
        topic="transformers",
        disciplines=["machine learning"],
        publication_date_range=(date(2022, 1, 1), date(2026, 1, 1)),
    )
    paper = Paper(
        arxiv_id="2301.12345",
        title="Test",
        authors=["A"],
        abstract="Abstract",
        published_date=date(2023, 1, 1),
    )
    episode = Episode(
        episode_id="2026-03-04_transformers_ab12",
        query=qp,
        papers=[paper],
        created_at=datetime(2026, 3, 4, 10, 0, 0),
    )
    assert episode.audio_path is None
    assert len(episode.papers) == 1
