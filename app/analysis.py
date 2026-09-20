

from __future__ import annotations

from collections import Counter, defaultdict
from dataclasses import asdict, dataclass
from datetime import datetime
import math
import re
from statistics import mean, pstdev
from typing import Any, Iterable, Optional


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

WORD_RE = re.compile(r"[A-Za-zÀ-ÖØ-öø-ÿ0-9']+")
SENTENCE_RE = re.compile(r"[.!?]+")

PUNCTUATION_CHARS = set("!?;,:-")
COMMON_FUNCTION_WORDS = {
    "the",
    "a",
    "an",
    "and",
    "or",
    "but",
    "if",
    "then",
    "than",
    "for",
    "from",
    "with",
    "without",
    "to",
    "of",
    "in",
    "on",
    "at",
    "by",
    "is",
    "are",
    "was",
    "were",
    "be",
    "been",
    "have",
    "has",
    "had",
    "do",
    "does",
    "did",
    "not",
    "this",
    "that",
    "it",
    "as",
}


# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------

@dataclass
class StylometricProfile:
    status: str
    posts: int = 0
    words: int = 0
    characters: int = 0

    avg_word_length: float = 0.0
    word_length_stddev: float = 0.0

    avg_sentence_length: float = 0.0
    sentence_length_stddev: float = 0.0

    type_token_ratio: float = 0.0
    hapax_ratio: float = 0.0

    punctuation_density: float = 0.0
    exclamation_ratio: float = 0.0
    question_ratio: float = 0.0

    uppercase_ratio: float = 0.0
    digit_ratio: float = 0.0

    function_word_ratio: float = 0.0
    average_paragraph_length: float = 0.0

    emoji_count: int = 0
    url_count: int = 0

    @property
    def usable(self) -> bool:
        return self.status == "ok" and self.words >= 20


@dataclass
class BehavioralProfile:
    status: str
    posts: int = 0

    posting_hours: list[int] | None = None
    posting_weekdays: list[int] | None = None

    categories: dict[str, int] | None = None
    activity_concentration: float = 0.0

    avg_post_length: float = 0.0
    post_length_stddev: float = 0.0

    active_hours: int = 0
    active_days: int = 0

    @property
    def usable(self) -> bool:
        return self.status == "ok" and self.posts >= 2


@dataclass
class SimilarityResult:
    status: str
    score: float
    confidence: float
    dimensions: dict[str, float]
    evidence: list[str]
    limitations: list[str]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


# ---------------------------------------------------------------------------
# Normalization helpers
# ---------------------------------------------------------------------------

def _safe_text(value: Any) -> str:
    if value is None:
        return ""
    return str(value).strip()


def _extract_text(post: dict[str, Any]) -> str:
    """
    Accept several common crawler/OSINT field names.

    This keeps analysis compatible with raw crawler records without forcing
    every upstream module to use exactly the same field name.
    """
    for key in (
        "content",
        "text",
        "body",
        "message",
        "post_content",
        "description",
        "excerpt",
    ):
        value = post.get(key)
        if value:
            return _safe_text(value)

    return ""


def tokenize(text: str) -> list[str]:
    return WORD_RE.findall(_safe_text(text).lower())


def _sentences(text: str) -> list[str]:
    text = _safe_text(text)
    if not text:
        return []

    return [
        item.strip()
        for item in SENTENCE_RE.split(text)
        if item.strip()
    ]


def _parse_timestamp(value: Any) -> Optional[datetime]:
    if not value:
        return None

    if isinstance(value, datetime):
        return value

    raw = _safe_text(value)

    # ISO timestamps.
    try:
        return datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except ValueError:
        pass

    # Common crawler timestamp formats.
    formats = (
        "%Y-%m-%d %H:%M:%S",
        "%Y-%m-%d",
        "%d-%m-%Y %H:%M:%S",
        "%d-%m-%Y",
        "%d/%m/%Y %H:%M:%S",
        "%d/%m/%Y",
    )

    for fmt in formats:
        try:
            return datetime.strptime(raw, fmt)
        except ValueError:
            continue

    return None


def _safe_ratio(numerator: float, denominator: float) -> float:
    if denominator <= 0:
        return 0.0
    return numerator / denominator


def _clamp(value: float, low: float = 0.0, high: float = 1.0) -> float:
    return max(low, min(high, float(value)))


# ---------------------------------------------------------------------------
# Stylometry
# ---------------------------------------------------------------------------

def stylometry(posts: Iterable[dict[str, Any]]) -> dict[str, Any]:
    """
    Extract conservative stylometric features from a collection of posts.

    The output is descriptive. It does not claim that two profiles belong
    to the same person.
    """
    posts = list(posts or [])

    texts = [_extract_text(post) for post in posts]
    texts = [text for text in texts if text]

    if not texts:
        return asdict(
            StylometricProfile(
                status="insufficient_data",
                posts=0,
            )
        )

    words_per_post = [tokenize(text) for text in texts]
    words = [word for post_words in words_per_post for word in post_words]

    if not words:
        return asdict(
            StylometricProfile(
                status="insufficient_data",
                posts=len(texts),
            )
        )

    word_lengths = [len(word) for word in words]

    sentence_lengths: list[int] = []

    for text in texts:
        sentences = _sentences(text)

        for sentence in sentences:
            sentence_words = tokenize(sentence)
            if sentence_words:
                sentence_lengths.append(len(sentence_words))

    if not sentence_lengths:
        sentence_lengths = [len(words)]

    characters = sum(len(text) for text in texts)

    word_counter = Counter(words)

    punctuation_count = sum(
        1
        for text in texts
        for char in text
        if char in PUNCTUATION_CHARS
    )

    exclamation_count = sum(
        text.count("!")
        for text in texts
    )

    question_count = sum(
        text.count("?")
        for text in texts
    )

    uppercase_count = sum(
        1
        for text in texts
        for char in text
        if char.isalpha() and char.isupper()
    )

    alphabetic_count = sum(
        1
        for text in texts
        for char in text
        if char.isalpha()
    )

    digit_count = sum(
        1
        for text in texts
        for char in text
        if char.isdigit()
    )

    function_words = sum(
        1
        for word in words
        if word in COMMON_FUNCTION_WORDS
    )

    paragraph_lengths: list[int] = []

    for text in texts:
        paragraphs = [
            paragraph.strip()
            for paragraph in re.split(r"\n\s*\n", text)
            if paragraph.strip()
        ]

        for paragraph in paragraphs:
            paragraph_lengths.append(len(tokenize(paragraph)))

    if not paragraph_lengths:
        paragraph_lengths = [len(words)]

    emoji_count = sum(
        1
        for text in texts
        if any(
            ord(char) > 0x1F000
            for char in text
        )
    )

    url_count = sum(
        len(
            re.findall(
                r"https?://\S+|www\.\S+",
                text,
                flags=re.IGNORECASE,
            )
        )
        for text in texts
    )

    unique_words = len(word_counter)

    hapax_words = sum(
        1
        for count in word_counter.values()
        if count == 1
    )

    profile = StylometricProfile(
        status="ok",
        posts=len(texts),
        words=len(words),
        characters=characters,

        avg_word_length=round(
            mean(word_lengths),
            4,
        ),

        word_length_stddev=round(
            pstdev(word_lengths) if len(word_lengths) > 1 else 0.0,
            4,
        ),

        avg_sentence_length=round(
            mean(sentence_lengths),
            4,
        ),

        sentence_length_stddev=round(
            pstdev(sentence_lengths)
            if len(sentence_lengths) > 1
            else 0.0,
            4,
        ),

        type_token_ratio=round(
            _safe_ratio(unique_words, len(words)),
            4,
        ),

        hapax_ratio=round(
            _safe_ratio(hapax_words, unique_words),
            4,
        ),

        punctuation_density=round(
            _safe_ratio(punctuation_count, characters),
            6,
        ),

        exclamation_ratio=round(
            _safe_ratio(exclamation_count, characters),
            6,
        ),

        question_ratio=round(
            _safe_ratio(question_count, characters),
            6,
        ),

        uppercase_ratio=round(
            _safe_ratio(uppercase_count, alphabetic_count),
            6,
        ),

        digit_ratio=round(
            _safe_ratio(digit_count, characters),
            6,
        ),

        function_word_ratio=round(
            _safe_ratio(function_words, len(words)),
            6,
        ),

        average_paragraph_length=round(
            mean(paragraph_lengths),
            4,
        ),

        emoji_count=emoji_count,
        url_count=url_count,
    )

    return asdict(profile)


# ---------------------------------------------------------------------------
# Behavioral analysis
# ---------------------------------------------------------------------------

def behavior(posts: Iterable[dict[str, Any]]) -> dict[str, Any]:
    """
    Extract observable posting behavior.

    Behavioral features are descriptive and should not be treated as proof
    of identity or intent.
    """
    posts = list(posts or [])

    if not posts:
        return asdict(
            BehavioralProfile(
                status="insufficient_data",
                posts=0,
                posting_hours=[],
                posting_weekdays=[],
                categories={},
            )
        )

    hours: list[int] = []
    weekdays: list[int] = []
    categories: Counter[str] = Counter()
    lengths: list[int] = []

    for post in posts:
        text = _extract_text(post)

        if text:
            lengths.append(len(tokenize(text)))

        category = (
            post.get("category")
            or post.get("forum_category")
            or post.get("topic")
        )

        if category:
            categories[_safe_text(category)] += 1

        timestamp = (
            post.get("timestamp_parsed")
            or post.get("timestamp")
            or post.get("created_at")
            or post.get("date")
            or post.get("posted_at")
        )

        parsed = _parse_timestamp(timestamp)

        if parsed:
            hours.append(parsed.hour)
            weekdays.append(parsed.weekday())

    activity_concentration = 0.0

    if categories:
        activity_concentration = (
            max(categories.values()) / len(posts)
        )

    profile = BehavioralProfile(
        status="ok",
        posts=len(posts),

        posting_hours=sorted(set(hours)),
        posting_weekdays=sorted(set(weekdays)),

        categories=dict(categories),

        activity_concentration=round(
            activity_concentration,
            4,
        ),

        avg_post_length=round(
            mean(lengths) if lengths else 0.0,
            4,
        ),

        post_length_stddev=round(
            pstdev(lengths)
            if len(lengths) > 1
            else 0.0,
            4,
        ),

        active_hours=len(set(hours)),
        active_days=len(set(weekdays)),
    )

    return asdict(profile)


# ---------------------------------------------------------------------------
# Generic numeric similarity
# ---------------------------------------------------------------------------

def _relative_similarity(
    a: float,
    b: float,
    scale: Optional[float] = None,
) -> float:
    """
    Convert two numeric measurements into a bounded similarity value.

    This is deliberately simple and interpretable.
    """
    a = float(a)
    b = float(b)

    denominator = scale

    if denominator is None:
        denominator = abs(a) + abs(b)

    if denominator <= 1e-12:
        return 1.0

    return _clamp(
        1.0 - abs(a - b) / denominator
    )


def _distribution_similarity(
    a: Iterable[int],
    b: Iterable[int],
    period: int,
) -> float:
    """
    Compare two sets of periodic activity points.

    Example:
    - hours → period 24
    - weekdays → period 7
    """
    a_set = set(a or [])
    b_set = set(b or [])

    if not a_set or not b_set:
        return 0.0

    intersection = len(a_set & b_set)
    union = len(a_set | b_set)

    return _safe_ratio(intersection, union)


# ---------------------------------------------------------------------------
# Stylometric comparison
# ---------------------------------------------------------------------------

def compare(
    a: dict[str, Any],
    b: dict[str, Any],
) -> float:
    """
    Backwards-compatible stylometric similarity function.

    Returns a value from 0.0 to 1.0.
    """
    result = compare_stylometry(a, b)
    return result["score"]


def compare_stylometry(
    a: dict[str, Any],
    b: dict[str, Any],
) -> dict[str, Any]:
    """
    Compare two stylometric profiles.

    Important:
    This measures similarity of observed writing features only.
    It does not identify the author.
    """
    keys = (
        "avg_word_length",
        "word_length_stddev",
        "avg_sentence_length",
        "sentence_length_stddev",
        "type_token_ratio",
        "hapax_ratio",
        "punctuation_density",
        "exclamation_ratio",
        "question_ratio",
        "uppercase_ratio",
        "digit_ratio",
        "function_word_ratio",
        "average_paragraph_length",
    )

    similarities: dict[str, float] = {}

    for key in keys:
        x = a.get(key)
        y = b.get(key)

        if not isinstance(x, (int, float)):
            continue

        if not isinstance(y, (int, float)):
            continue

        x = float(x)
        y = float(y)

        if key in {
            "type_token_ratio",
            "hapax_ratio",
            "punctuation_density",
            "exclamation_ratio",
            "question_ratio",
            "uppercase_ratio",
            "digit_ratio",
            "function_word_ratio",
        }:
            similarity = _relative_similarity(
                x,
                y,
                scale=max(abs(x), abs(y), 0.0001),
            )
        else:
            similarity = _relative_similarity(x, y)

        similarities[key] = round(
            similarity,
            4,
        )

    if not similarities:
        return {
            "status": "insufficient_data",
            "score": 0.0,
            "dimensions": {},
        }

    score = mean(similarities.values())

    return {
        "status": "ok",
        "score": round(
            _clamp(score),
            4,
        ),
        "dimensions": similarities,
    }


# ---------------------------------------------------------------------------
# Behavioral comparison
# ---------------------------------------------------------------------------

def compare_behavior(
    a: dict[str, Any],
    b: dict[str, Any],
) -> dict[str, Any]:
    dimensions: dict[str, float] = {}

    dimensions["posting_hours"] = round(
        _distribution_similarity(
            a.get("posting_hours", []),
            b.get("posting_hours", []),
            24,
        ),
        4,
    )

    dimensions["posting_weekdays"] = round(
        _distribution_similarity(
            a.get("posting_weekdays", []),
            b.get("posting_weekdays", []),
            7,
        ),
        4,
    )

    if (
        isinstance(a.get("avg_post_length"), (int, float))
        and isinstance(b.get("avg_post_length"), (int, float))
    ):
        dimensions["avg_post_length"] = round(
            _relative_similarity(
                float(a["avg_post_length"]),
                float(b["avg_post_length"]),
            ),
            4,
        )

    if (
        isinstance(a.get("post_length_stddev"), (int, float))
        and isinstance(b.get("post_length_stddev"), (int, float))
    ):
        dimensions["post_length_variability"] = round(
            _relative_similarity(
                float(a["post_length_stddev"]),
                float(b["post_length_stddev"]),
            ),
            4,
        )

    categories_a = set(
        (a.get("categories") or {}).keys()
    )

    categories_b = set(
        (b.get("categories") or {}).keys()
    )

    if categories_a or categories_b:
        union = categories_a | categories_b
        intersection = categories_a & categories_b

        dimensions["categories"] = round(
            _safe_ratio(
                len(intersection),
                len(union),
            ),
            4,
        )

    if not dimensions:
        return {
            "status": "insufficient_data",
            "score": 0.0,
            "dimensions": {},
        }

    score = mean(dimensions.values())

    return {
        "status": "ok",
        "score": round(
            _clamp(score),
            4,
        ),
        "dimensions": dimensions,
    }


# ---------------------------------------------------------------------------
# Combined persona comparison
# ---------------------------------------------------------------------------

def compare_personas(
    profile_a: dict[str, Any],
    profile_b: dict[str, Any],
    stylometry_weight: float = 0.70,
    behavior_weight: float = 0.30,
) -> dict[str, Any]:
    """
    Produce an evidence-aware comparison between two observed profiles.

    Stylometry is weighted more heavily than behavior because behavioral
    features are generally more contextual and easier to share between
    unrelated users.

    The resulting score is a similarity lead, NOT an identity probability.
    """
    style_a = profile_a.get("stylometry") or {}
    style_b = profile_b.get("stylometry") or {}

    behavior_a = profile_a.get("behavior") or {}
    behavior_b = profile_b.get("behavior") or {}

    style_result = compare_stylometry(
        style_a,
        style_b,
    )

    behavior_result = compare_behavior(
        behavior_a,
        behavior_b,
    )

    available_dimensions = []

    if style_result["status"] == "ok":
        available_dimensions.append(
            (
                style_result["score"],
                stylometry_weight,
            )
        )

    if behavior_result["status"] == "ok":
        available_dimensions.append(
            (
                behavior_result["score"],
                behavior_weight,
            )
        )

    if not available_dimensions:
        return SimilarityResult(
            status="insufficient_data",
            score=0.0,
            confidence=0.0,
            dimensions={},
            evidence=[],
            limitations=[
                "Insufficient comparable stylometric or behavioral data.",
            ],
        ).to_dict()

    total_weight = sum(
        weight
        for _, weight in available_dimensions
    )

    score = sum(
        value * weight
        for value, weight in available_dimensions
    ) / total_weight

    evidence: list[str] = []
    limitations: list[str] = []

    if style_result["status"] == "ok":
        evidence.append(
            f"Stylometric similarity: "
            f"{style_result['score']:.2f}"
        )
    else:
        limitations.append(
            "Stylometric comparison could not be performed "
            "with sufficient data."
        )

    if behavior_result["status"] == "ok":
        evidence.append(
            f"Behavioral similarity: "
            f"{behavior_result['score']:.2f}"
        )
    else:
        limitations.append(
            "Behavioral comparison could not be performed "
            "with sufficient data."
        )

    # Confidence represents quality/support of the comparison,
    # not probability that both profiles belong to the same person.
    confidence = calculate_analysis_confidence(
        profile_a,
        profile_b,
    )

    limitations.extend(
        [
            "Similarity does not establish identity.",
            "Shared writing style or activity patterns may occur "
            "between unrelated users.",
            "Attribution should require corroborating identifiers "
            "and independent evidence.",
        ]
    )

    return SimilarityResult(
        status="ok",
        score=round(
            _clamp(score),
            4,
        ),
        confidence=round(
            confidence,
            4,
        ),
        dimensions={
            "stylometry": round(
                style_result["score"],
                4,
            ),
            "behavior": round(
                behavior_result["score"],
                4,
            ),
        },
        evidence=evidence,
        limitations=limitations,
    ).to_dict()


# ---------------------------------------------------------------------------
# Confidence
# ---------------------------------------------------------------------------

def _data_quality(
    profile: dict[str, Any],
) -> float:
    """
    Estimate whether a profile has enough observations for comparison.

    This is a data-quality measure, not an attribution probability.
    """
    style = profile.get("stylometry") or {}
    behavior_profile = profile.get("behavior") or {}

    style_words = int(
        style.get("words") or 0
    )

    style_posts = int(
        style.get("posts") or 0
    )

    behavior_posts = int(
        behavior_profile.get("posts") or 0
    )

    style_quality = _clamp(
        math.log10(max(style_words, 1)) / 3.0
    )

    post_quality = _clamp(
        style_posts / 20.0
    )

    behavior_quality = _clamp(
        behavior_posts / 20.0
    )

    return _clamp(
        (
            style_quality * 0.55
            + post_quality * 0.25
            + behavior_quality * 0.20
        )
    )


def calculate_analysis_confidence(
    profile_a: dict[str, Any],
    profile_b: dict[str, Any],
) -> float:
    quality_a = _data_quality(profile_a)
    quality_b = _data_quality(profile_b)

    return round(
        min(quality_a, quality_b),
        4,
    )


# ---------------------------------------------------------------------------
# Complete analysis
# ---------------------------------------------------------------------------

def analyze_posts(
    posts: Iterable[dict[str, Any]],
) -> dict[str, Any]:
    """
    Generate the complete analysis profile for one observed account/source.
    """
    posts = list(posts or [])

    style = stylometry(posts)
    behavior_profile = behavior(posts)

    return {
        "status": (
            "ok"
            if (
                style.get("status") == "ok"
                or behavior_profile.get("status") == "ok"
            )
            else "insufficient_data"
        ),
        "stylometry": style,
        "behavior": behavior_profile,
        "analysis_version": "2.0",
    }


# ---------------------------------------------------------------------------
# Multi-profile comparison
# ---------------------------------------------------------------------------

def compare_multiple_profiles(
    reference_profile: dict[str, Any],
    candidate_profiles: Iterable[dict[str, Any]],
) -> list[dict[str, Any]]:
    """
    Compare one reference profile against multiple candidate profiles.

    Results are sorted by similarity for investigation convenience.

    This is an ordering of similarity measurements, not an attribution
    ranking or identity conclusion.
    """
    results: list[dict[str, Any]] = []

    for candidate in candidate_profiles:
        result = compare_personas(
            reference_profile,
            candidate,
        )

        result["candidate_id"] = (
            candidate.get("actor_id")
            or candidate.get("profile_id")
            or candidate.get("id")
        )

        results.append(result)

    results.sort(
        key=lambda item: (
            float(item.get("score") or 0.0)
        ),
        reverse=True,
    )

    return results


# ---------------------------------------------------------------------------
# Database persistence
# ---------------------------------------------------------------------------

def persist_analysis(
    db: Any,
    investigation_id: str,
    posts: Iterable[dict[str, Any]],
    actor_id: Optional[str] = None,
    run_id: Optional[str] = None,
) -> dict[str, Any]:
    """
    Persist analysis observations through the PRALAYX database layer.

    The analysis result itself is preserved as a raw snapshot so the exact
    generated result can be inspected later without overwriting previous runs.
    """
    posts = list(posts or [])

    result = analyze_posts(posts)

    if db is None:
        return result

    metadata = {
        "analysis_version": result["analysis_version"],
        "posts": len(posts),
    }

    try:
        db.add_raw_snapshot(
            investigation_id=investigation_id,
            snapshot_type="analysis",
            payload=result,
            session_id=None,
            run_id=run_id,
        )
    except TypeError:
        # Compatibility with older database wrappers.
        try:
            db.add_raw_snapshot(
                investigation_id,
                "analysis",
                result,
                run_id=run_id,
            )
        except Exception:
            pass
    except Exception:
        pass

    style = result.get("stylometry") or {}
    behavior_profile = result.get("behavior") or {}

    # Persist high-value observable features as entity sightings.
    try:
        if style.get("status") == "ok":
            db.add_observation(
                investigation_id=investigation_id,
                entity_type="stylometry_profile",
                entity_value=f"{style.get('words', 0)}_words",
                actor_id=actor_id,
                confidence=None,
                metadata={
                    **metadata,
                    "stylometry": style,
                },
                run_id=run_id,
            )
    except Exception:
        pass

    try:
        if behavior_profile.get("status") == "ok":
            db.add_observation(
                investigation_id=investigation_id,
                entity_type="behavior_profile",
                entity_value=f"{behavior_profile.get('posts', 0)}_posts",
                actor_id=actor_id,
                confidence=None,
                metadata={
                    **metadata,
                    "behavior": behavior_profile,
                },
                run_id=run_id,
            )
    except Exception:
        pass

    try:
        db.add_timeline_event(
            investigation_id=investigation_id,
            event_type="analysis_completed",
            message=(
                "Stylometry and behavioral analysis completed"
            ),
            run_id=run_id,
            actor_id=actor_id,
            metadata=result,
        )
    except TypeError:
        try:
            db.add_timeline_event(
                investigation_id,
                "analysis_completed",
                "Stylometry and behavioral analysis completed",
                run_id=run_id,
                actor_id=actor_id,
                metadata=result,
            )
        except Exception:
            pass
    except Exception:
        pass

    return result


# ---------------------------------------------------------------------------
# Legacy compatibility
# ---------------------------------------------------------------------------

def analyze(
    posts: Iterable[dict[str, Any]],
) -> dict[str, Any]:
    """
    Backwards-compatible alias used by older platform code.
    """
    return analyze_posts(posts)


__all__ = [
    "StylometricProfile",
    "BehavioralProfile",
    "SimilarityResult",
    "tokenize",
    "stylometry",
    "behavior",
    "compare",
    "compare_stylometry",
    "compare_behavior",
    "compare_personas",
    "compare_multiple_profiles",
    "calculate_analysis_confidence",
    "analyze_posts",
    "analyze",
    "persist_analysis",
]
