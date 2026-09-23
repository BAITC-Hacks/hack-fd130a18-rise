"""Score and deterministically sort profiles that passed hard filters."""

from __future__ import annotations

import re
from typing import Any, Iterable


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


def _description_score(description: str, query: dict[str, Any]) -> int:
    """Give points only for literal query terms found in profile evidence."""
    text = _normalized(description)
    terms = [query.get("category"), query.get("event_type"), query.get("language")]
    points = 0
    for term in terms:
        normalized_term = _normalized(term)
        if normalized_term and normalized_term in text:
            points += 2 if normalized_term == _normalized(query.get("category")) else 1
    return min(points, 4)


def _price_score(price: Any, budget: int) -> int:
    """Reward headroom under the user's maximum budget, up to 15 points."""
    if price is None or str(price).strip() == "" or budget <= 0:
        return 0
    try:
        price_value = int(price)
    except (TypeError, ValueError):
        return 0
    if price_value < 0 or price_value > budget:
        return 0
    return round(15 * (budget - price_value) / budget)


def rank_profiles(
    profiles: Iterable[dict[str, Any]], query: dict[str, Any]
) -> list[dict[str, Any]]:
    """Return copied profiles with scores, ordered by score then stable ID.

    This function expects profiles to have already passed filters.py. Exact
    city/category/format matching and any requested language/hours constraints
    are therefore confirmed facts and contribute fixed points. Lower starting
    prices within budget receive more price-fit points. Description points
    come only from literal mentions of the requested category, event format,
    or language. Non-synthetic profiles receive a small provenance bonus; this
    does not remove synthetic profiles from the results.

    ``score_parts`` values explain every point group and sum exactly to
    ``score``. Original profile dictionaries are not modified.
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

        hours_requested = query.get("hours") is not None
        max_hours = profile.get("max_hours")
        hours_match = True
        if hours_requested and max_hours is not None and str(max_hours).strip():
            try:
                hours_match = float(query["hours"]) <= float(max_hours)
            except (TypeError, ValueError):
                hours_match = False

        parts = {
            "category_match": 40 if city_match and category_match else 0,
            "event_format_match": 20 if format_match else 0,
            "language_match": 10 if language_requested and language_match else 0,
            "hours_match": 5 if hours_requested and hours_match else 0,
            "price_fit": _price_score(profile.get("price_from_kzt"), budget),
            "description_relevance": _description_score(
                str(profile.get("description") or ""), query
            ),
            "real_profile": 5 if not bool(profile.get("synthetic", False)) else 0,
        }

        item = dict(profile)
        item["score_parts"] = parts
        item["score"] = sum(parts.values())
        ranked.append(item)

    # Sorting only on stable primitive values makes repeated requests stable.
    ranked.sort(key=lambda item: (-item["score"], str(item.get("id") or "")))
    return ranked
