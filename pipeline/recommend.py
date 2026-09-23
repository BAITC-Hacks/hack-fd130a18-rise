"""Connect data loading, hard filters, ranking, and factual explanations."""

from __future__ import annotations

from collections import Counter
from typing import Any

from pipeline.explain import explain_profile
from pipeline.filters import filter_profiles
from pipeline.load import load_profiles
from pipeline.ranking import rank_profiles


MAX_CARDS = 3

REASON_LABELS = {
    "busy_date": "занят на выбранную дату",
    "over_budget": "цена выше бюджета",
    "price_unknown": "цену нельзя проверить по бюджету",
    "format_mismatch": "не указан нужный формат мероприятия",
    "language_mismatch": "не указан нужный язык",
    "hours_exceeded": "запрошенная длительность превышает лимит",
    "hours_unknown": "некорректно указано ограничение по часам",
}


def _reason_summary(rejected: list[dict[str, Any]]) -> str:
    counts: Counter[str] = Counter(
        reason["code"]
        for profile in rejected
        for reason in profile.get("reasons", [])
    )
    if not counts:
        return ""
    return "; ".join(
        f"{count} — {REASON_LABELS.get(code, code)}"
        for code, count in sorted(counts.items())
    )


def _make_card(profile: dict[str, Any], query: dict[str, Any]) -> dict[str, Any]:
    busy_dates = profile.get("busy_dates") or []
    if isinstance(busy_dates, str):
        busy_dates = [part.strip() for part in busy_dates.split("|") if part.strip()]
    date = str(query["date"])
    if busy_dates:
        availability = f"Свободен(на) {date} по календарю профиля"
    else:
        availability = f"Дата {date} не отмечена как занятая; календарь профиля пуст"

    notes: list[str] = []
    if profile.get("synthetic"):
        notes.append("Синтетический профиль")
    if profile.get("city_imputed"):
        notes.append("Город восстановлен при подготовке датасета")
    if profile.get("price_imputed"):
        notes.append("Цена восстановлена при подготовке датасета")

    return {
        "id": profile.get("id"),
        "name": profile.get("anon_name") or profile.get("name") or "Без имени",
        "categories": profile.get("categories") or [],
        "city": profile.get("city") or "",
        "price": profile.get("price_from_kzt"),
        "synthetic": bool(profile.get("synthetic", False)),
        "score": profile["score"],
        "score_parts": profile["score_parts"],
        "explanation": explain_profile(profile, query),
        "availability": availability,
        "notes": notes,
    }


def recommend(query: dict[str, Any]) -> dict[str, Any]:
    """Return up to three deterministic contractor recommendations.

    ``query`` uses the agreed fields: city, date, event_type, category, budget,
    hours (number or None), and language (string or None). Profiles are loaded
    from the default CSV location defined in pipeline/load.py.
    """
    profiles = load_profiles()
    filtered = filter_profiles(profiles, query)
    rejected = filtered["rejected"]
    category_count = filtered["category_count"]
    rejected_count = filtered["rejected_count"]
    reason_text = _reason_summary(rejected)

    if filtered["outcome"] == "no_category":
        headline = "В этом городе такой категории нет"
        summary = (
            f"В городе {query['city']} не найдено профилей категории "
            f"«{query['category']}»."
        )
        cards: list[dict[str, Any]] = []
    elif filtered["outcome"] == "none_passed":
        headline = "Кандидаты есть, но никто не проходит условия"
        summary = (
            f"В категории найдено профилей: {category_count}. "
            f"Отсеяно фильтрами: {rejected_count}. Причины: {reason_text or 'условия не совпали'}."
        )
        cards = []
    else:
        ranked = rank_profiles(filtered["passed"], query)
        selected = ranked[:MAX_CARDS]
        cards = [_make_card(profile, query) for profile in selected]
        headline = "Подобрали подрядчиков"
        summary = (
            f"В категории найдено профилей: {category_count}. "
            f"Прошли условия: {filtered['passed_count']}; отсеяно: {rejected_count}."
        )
        if reason_text:
            summary += f" Причины отказа: {reason_text}."
        if filtered["passed_count"] > MAX_CARDS:
            summary += f" Показаны первые {MAX_CARDS} по рейтингу."
        elif filtered["passed_count"] < MAX_CARDS:
            summary += f" Подходящих меньше трёх: найдено {filtered['passed_count']}."

    return {
        "outcome": filtered["outcome"],
        "headline": headline,
        "summary": summary,
        "cards": cards,
        "rejected": rejected,
    }
