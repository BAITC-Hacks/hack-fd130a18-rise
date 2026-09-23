"""Score and deterministically sort profiles that passed hard filters."""

from __future__ import annotations

import json
from math import inf, sqrt
from typing import Any, Iterable


FORMAT_ROOTS = {
    "свадьба": ("свадьб", "свадеб", "свадебн", "невест", "молодожен", "молодожён"),
    "той": ("той", "тоя", "тоев", "узату", "сундет", "традиц", "национальн"),
    "корпоратив": ("корпорат", "компани", "бренд", "сотрудник", "бизнес"),
    "конференция": ("конференц", "форум", "делов", "презентац"),
    "юбилей": ("юбиле",),
    "день рождения": ("день рождения", "дня рождения", "дни рождения", "детск"),
}


def _normalized(value: Any) -> str:
    return str(value or "").strip().casefold()


def _values(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        return [part.strip() for part in value.split("|") if part.strip()]
    try:
        return [str(part).strip() for part in value if str(part).strip()]
    except TypeError:
        return [str(value).strip()]


def _as_bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    return _normalized(value) in {"true", "1", "yes", "да"}


def _price_fit_score(price: Any, budget: int) -> int:
    """Prefer prices in the requested 50–85% budget band (max 30 points)."""
    try:
        price_value = float(price)
    except (TypeError, ValueError):
        return 0
    if budget <= 0 or price_value < 0 or price_value > budget:
        return 0

    ratio = price_value / budget
    if ratio < 0.50:
        return round(24 * ratio / 0.50)
    if ratio <= 0.85:
        midpoint = (0.50 + 0.85) / 2
        half_width = (0.85 - 0.50) / 2
        return round(24 + 6 * (1 - abs(ratio - midpoint) / half_width))
    return round(24 * (1 - ratio) / 0.15)


def _hours_headroom_score(profile: dict[str, Any], query: dict[str, Any]) -> int:
    """Reward spare capacity for the event duration, up to 15 points."""
    requested_hours = query.get("hours")
    if requested_hours is None:
        return 0

    max_hours = profile.get("max_hours")
    if max_hours is None or str(max_hours).strip() == "":
        # The dataset defines an empty max_hours value as no duration limit.
        return 15

    try:
        spare_hours = float(max_hours) - float(requested_hours)
    except (TypeError, ValueError):
        return 0
    if spare_hours < 0:
        return 0
    return round(15 * min(spare_hours / 8, 1))


def _format_mentioned_score(profile: dict[str, Any], query: dict[str, Any]) -> int:
    requested_format = _normalized(query.get("event_type"))
    description = _normalized(profile.get("description"))
    roots = FORMAT_ROOTS.get(requested_format, ())
    matches = sum(1 for root in roots if root in description)
    return min(matches * 5, 15)


def _tie_break_price(profile: dict[str, Any]) -> float:
    try:
        return float(profile.get("price_from_kzt"))
    except (TypeError, ValueError):
        return inf


def rank_profiles(
    profiles: Iterable[dict[str, Any]], query: dict[str, Any]
) -> list[dict[str, Any]]:
    """Return copied profiles with score parts and stable ranking order.

    This function expects profiles to have passed filters.py. Score parts are
    explicit facts: city/category and format matches, requested language and
    duration, price fit, whether the description mentions the event format,
    and provenance flags. Negative score parts are penalties for imputed price
    or city. The final score is the sum of all score parts.

    Ties are resolved by lower starting price, then lexicographic profile ID.
    Input profile dictionaries are not modified.
    """
    try:
        budget = int(query["budget"])
    except (KeyError, TypeError, ValueError) as error:
        raise ValueError("Для ранжирования в query нужен числовой budget.") from error

    ranked: list[dict[str, Any]] = []
    for profile in profiles:
        categories = _values(profile.get("categories"))
        formats = _values(profile.get("event_formats"))
        languages = _values(profile.get("languages"))

        city_match = _normalized(profile.get("city")) == _normalized(query.get("city"))
        category_match = any(
            _normalized(value) == _normalized(query.get("category"))
            for value in categories
        )
        format_match = any(
            _normalized(value) == _normalized(query.get("event_type"))
            for value in formats
        )

        language_requested = bool(_normalized(query.get("language")))
        language_match = not language_requested or any(
            _normalized(value) == _normalized(query.get("language"))
            for value in languages
        )

        synthetic = _as_bool(profile.get("synthetic", False))
        price_imputed = _as_bool(profile.get("price_imputed", False))
        city_imputed = _as_bool(profile.get("city_imputed", False))

        parts = {
            "category_match": 30 if city_match and category_match else 0,
            "event_format_match": 10 if format_match else 0,
            "language_match": 5 if language_requested and language_match else 0,
            "price_fit": _price_fit_score(profile.get("price_from_kzt"), budget),
            "format_mentioned_in_description": _format_mentioned_score(profile, query),
            "hours_headroom": _hours_headroom_score(profile, query),
            "real_profile": 5 if not synthetic else 0,
            "price_imputed_penalty": -6 if price_imputed else 0,
            "city_imputed_penalty": -6 if city_imputed else 0,
        }

        item = dict(profile)
        item["score_parts"] = parts
        item["score"] = sum(parts.values())
        ranked.append(item)

    ranked.sort(
        key=lambda item: (
            -item["score"],
            _tie_break_price(item),
            str(item.get("id") or ""),
        )
    )
    return ranked


def cosine_similarity(vec1: list[float], vec2: list[float]) -> float:
    """Return cosine similarity, or zero when a vector has no length."""
    if len(vec1) != len(vec2):
        raise ValueError("Векторы должны иметь одинаковую размерность.")

    dot_product = sum(first * second for first, second in zip(vec1, vec2))
    length1 = sqrt(sum(value * value for value in vec1))
    length2 = sqrt(sum(value * value for value in vec2))
    if length1 == 0 or length2 == 0:
        return 0.0
    return dot_product / (length1 * length2)


def load_embeddings_from_file(
    file_path: str = "data/embeddings.json",
) -> dict[str, list[float]]:
    """Read precomputed card vectors, or return an empty dict if absent."""
    try:
        with open(file_path, "r", encoding="utf-8") as file:
            return json.load(file)
    except FileNotFoundError:
        return {}


def rank_cards_by_embedding(
    query_vector: list[float], cards_embeddings: dict[str, list[float]]
) -> list[tuple[str, float]]:
    """Sort card IDs by descending similarity, breaking ties by ID."""
    scores = [
        (card_id, cosine_similarity(query_vector, vector))
        for card_id, vector in cards_embeddings.items()
    ]
    return sorted(scores, key=lambda item: (-item[1], item[0]))
