"""Build specific, deterministic explanations from profile and query facts."""

from __future__ import annotations

import re
from typing import Any


def _values(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        return [part.strip() for part in value.split("|") if part.strip()]
    try:
        return [str(part).strip() for part in value if str(part).strip()]
    except TypeError:
        return [str(value).strip()]


def _money(value: Any) -> str:
    try:
        return f"{int(value):,}".replace(",", " ")
    except (TypeError, ValueError):
        return "не указана"


def _description_excerpt(description: Any, limit: int = 180) -> str:
    """Choose a short literal excerpt without inventing or rewriting facts."""
    text = re.sub(r"\s+", " ", str(description or "")).strip()
    text = text.lstrip("•-* ")
    if not text:
        return ""

    # Use the first complete sentence when one is available and reasonably short.
    match = re.search(r"^(.+?[.!?])(?:\s|$)", text)
    excerpt = match.group(1) if match else text
    if len(excerpt) > limit:
        excerpt = excerpt[: limit - 1].rsplit(" ", 1)[0].rstrip(" ,;:") + "…"
    return excerpt


def explain_profile(profile: dict[str, Any], query: dict[str, Any]) -> str:
    """Explain why a filtered profile matches, using only recorded facts.

    The explanation deliberately omits the contractor's name. The profile ID
    and concrete profile details keep explanations attributable and distinct
    when names are hidden. This function does not rank profiles or modify them.
    """
    profile_id = str(profile.get("id") or "без id")
    city = str(profile.get("city") or query.get("city") or "город не указан")
    categories = _values(profile.get("categories"))
    category = next(
        (
            item
            for item in categories
            if item.strip().casefold() == str(query.get("category") or "").strip().casefold()
        ),
        str(query.get("category") or "категория не указана"),
    )
    event_type = str(query.get("event_type") or "формат не указан")
    date = str(query.get("date") or "дата не указана")
    budget = query.get("budget")
    price = profile.get("price_from_kzt")

    sentences = [
        f"Профиль {profile_id}: подрядчик указан в городе {city}, категория — «{category}».",
    ]

    if price is not None and str(price).strip():
        try:
            price_value = int(price)
        except (TypeError, ValueError):
            sentences.append("Цена в профиле заполнена некорректно.")
        else:
            if budget is not None:
                sentences.append(
                    f"Цена начинается от {_money(price_value)} ₸ при бюджете {_money(budget)} ₸."
                )
            else:
                sentences.append(f"Цена начинается от {_money(price_value)} ₸.")
    else:
        sentences.append("Цена в профиле не указана.")

    formats = _values(profile.get("event_formats"))
    matched_format = next(
        (item for item in formats if item.casefold() == event_type.strip().casefold()),
        None,
    )
    if matched_format:
        sentences.append(f"В профиле указан формат «{matched_format}».")
    else:
        sentences.append(f"В профиле перечислены форматы: {', '.join(formats) or 'не указаны'}.")

    languages = _values(profile.get("languages"))
    requested_language = str(query.get("language") or "").strip()
    if requested_language:
        matched_language = next(
            (item for item in languages if item.casefold() == requested_language.casefold()),
            None,
        )
        if matched_language:
            sentences.append(f"Поддерживается запрошенный язык: {matched_language}.")
        else:
            sentences.append(f"Языки в профиле: {', '.join(languages) or 'не указаны'}.")
    elif languages:
        sentences.append(f"В профиле указаны языки: {', '.join(languages)}.")

    requested_hours = query.get("hours")
    if requested_hours is not None:
        max_hours = profile.get("max_hours")
        if max_hours is None or str(max_hours).strip() == "":
            sentences.append(
                f"Запрошенная длительность — {requested_hours} ч.; в профиле нет ограничения по часам."
            )
        else:
            sentences.append(
                f"Запрошено {requested_hours} ч.; максимум в профиле — {max_hours} ч."
            )
    elif profile.get("max_hours") is None or str(profile.get("max_hours")).strip() == "":
        sentences.append("В профиле указано, что работа не ограничена по часам.")
    else:
        sentences.append(f"Максимальная длительность по профилю — {profile['max_hours']} ч.")

    busy_dates = _values(profile.get("busy_dates"))
    if date in busy_dates:
        sentences.append(f"В календаре профиля дата {date} отмечена как занятая.")
    elif busy_dates:
        sentences.append(f"Дата {date} не указана среди занятых дат профиля.")
    else:
        sentences.append("В профиле не заполнен список занятых дат.")

    excerpt = _description_excerpt(profile.get("description"))
    if excerpt:
        sentences.append(f"В описании: «{excerpt}».")

    return " ".join(sentences)
