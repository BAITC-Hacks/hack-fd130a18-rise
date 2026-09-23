"""Connect data loading, hard filters, ranking, and factual explanations."""

from __future__ import annotations

from collections import Counter
from datetime import date
from math import inf
from typing import Any

from pipeline.explain import explain_profile
from pipeline.filters import filter_profiles
from pipeline.load import load_profiles
from pipeline.ranking import FORMAT_ROOTS, rank_profiles


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

CATEGORY_PLURALS = {
    "ведущий": "Ведущие",
    "флорист": "Флористы",
    "фотограф": "Фотографы",
    "банкетный зал": "Банкетные залы",
    "лайв-бэнд": "Лайв-бэнды",
}


def _as_values(value: Any) -> list[str]:
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
    return str(value or "").strip().casefold() in {"true", "1", "yes", "да"}


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


def _funnel(query: dict[str, Any], filtered: dict[str, Any]) -> list[dict[str, Any]]:
    category = str(query.get("category") or "Категория")
    city = str(query.get("city") or "город не указан")
    plural = CATEGORY_PLURALS.get(category.casefold(), category)
    category_profiles = filtered["category_profiles"]
    remaining_ids = {str(profile.get("id")) for profile in category_profiles}
    rejected_by_id = {
        str(profile.get("id")): profile for profile in filtered["rejected"]
    }

    steps = [{"step": f"{plural} в {city}", "count": len(remaining_ids)}]
    if not category_profiles:
        return steps

    try:
        event_date = date.fromisoformat(str(query["date"]))
        short_date = event_date.strftime("%d.%m")
    except (KeyError, TypeError, ValueError):
        short_date = str(query.get("date") or "дате")

    filter_steps: list[tuple[str, set[str]]] = [
        (
            f"Свободны {short_date}",
            {"busy_date"},
        ),
        (
            "Укладываются в бюджет",
            {"over_budget", "price_unknown"},
        ),
        (
            f"Берут формат «{query.get('event_type', '')}»",
            {"format_mismatch"},
        ),
    ]
    if query.get("hours") is not None:
        filter_steps.append(("Подходят по часам", {"hours_exceeded", "hours_unknown"}))
    if str(query.get("language") or "").strip():
        filter_steps.append(("Работают на нужном языке", {"language_mismatch"}))

    for label, reason_codes in filter_steps:
        remove_ids = set()
        for profile_id in remaining_ids:
            rejected = rejected_by_id.get(profile_id)
            if rejected and any(
                reason.get("code") in reason_codes
                for reason in rejected.get("reasons", [])
            ):
                remove_ids.add(profile_id)
        remaining_ids.difference_update(remove_ids)
        steps.append({"step": label, "count": len(remaining_ids)})

    shown_count = min(len(remaining_ids), MAX_CARDS)
    steps.append({"step": "Показано", "count": shown_count})
    return steps


def _format_mention_count(profile: dict[str, Any], query: dict[str, Any]) -> int:
    event_format = str(query.get("event_type") or "").strip().casefold()
    roots = FORMAT_ROOTS.get(event_format, ())
    description = str(profile.get("description") or "").casefold()
    return sum(1 for root in roots if root in description)


def _number_or_none(value: Any) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _distinctive_profiles(
    profiles: list[dict[str, Any]], query: dict[str, Any]
) -> list[str]:
    """Find one highest-priority unique fact per shown profile."""
    if len(profiles) <= 1:
        return [""] * len(profiles)

    prices = [_number_or_none(profile.get("price_from_kzt")) for profile in profiles]
    valid_prices = [price for price in prices if price is not None]
    unique_low_price_index: int | None = None
    if len(valid_prices) == len(profiles):
        lowest = min(valid_prices)
        if valid_prices.count(lowest) == 1:
            unique_low_price_index = valid_prices.index(lowest)

    language_sets = [
        {language.casefold() for language in _as_values(profile.get("languages"))}
        for profile in profiles
    ]
    unique_languages: list[str | None] = []
    for index, languages in enumerate(language_sets):
        others = set().union(*(language_sets[:index] + language_sets[index + 1 :]))
        exclusive = sorted(languages - others)
        unique_languages.append(exclusive[0] if exclusive else None)

    hour_limits: list[float] = []
    for profile in profiles:
        max_hours = profile.get("max_hours")
        if max_hours is None or str(max_hours).strip() == "":
            hour_limits.append(inf)
        else:
            hour_limits.append(_number_or_none(max_hours) or 0.0)
    highest_hours = max(hour_limits)
    unique_high_hours_index = (
        hour_limits.index(highest_hours)
        if hour_limits.count(highest_hours) == 1
        else None
    )

    format_counts = [_format_mention_count(profile, query) for profile in profiles]
    highest_format_count = max(format_counts)
    unique_format_index = (
        format_counts.index(highest_format_count)
        if highest_format_count > 0 and format_counts.count(highest_format_count) == 1
        else None
    )

    result: list[str] = []
    for index, profile in enumerate(profiles):
        if index == unique_low_price_index:
            result.append(
                f"Самая низкая цена среди показанных: "
                f"{int(prices[index]):,}".replace(",", " ") + " ₸."
            )
        elif unique_languages[index] is not None:
            display_language = next(
                language
                for language in _as_values(profile.get("languages"))
                if language.casefold() == unique_languages[index]
            )
            result.append(f"Единственный среди показанных с языком {display_language}.")
        elif index == unique_high_hours_index:
            if hour_limits[index] == inf:
                result.append("Единственный среди показанных без лимита по часам.")
            else:
                result.append(
                    f"Больше всех часов на площадке: {hour_limits[index]:g} ч."
                )
        elif index == unique_format_index:
            result.append(
                f"Больше всех упоминаний формата «{query.get('event_type', '')}» "
                f"в описании: {format_counts[index]}."
            )
        else:
            result.append("")
    return result


SCORE_PART_LABELS = {
    "category_match": "совпадение города и категории",
    "event_format_match": "совпадение формата",
    "language_match": "совпадение языка",
    "price_fit": "соответствие цены бюджету",
    "format_mentioned_in_description": "упоминания формата в описании",
    "hours_headroom": "запас по часам",
    "real_profile": "признак реального профиля",
    "price_imputed_penalty": "признак восстановленной цены",
    "city_imputed_penalty": "признак восстановленного города",
}


def _rank_reason(
    position: int,
    profile: dict[str, Any],
    first_profile: dict[str, Any],
    query: dict[str, Any],
) -> str:
    if position == 1:
        return "Наибольший балл среди прошедших фильтры"

    parts = profile.get("score_parts") or {}
    first_parts = first_profile.get("score_parts") or {}
    common_keys = [key for key in first_parts if key in parts]
    if not common_keys:
        return f"{position}-е место: балл ниже, чем у {first_profile.get('anon_name') or 'первой карточки'}"

    key = max(common_keys, key=lambda item: abs(first_parts[item] - parts[item]))
    first_value = first_parts[key]
    value = parts[key]
    first_name = first_profile.get("anon_name") or "первой карточки"
    prefix = f"{position}-е место: "

    if key == "price_imputed_penalty":
        if value < first_value:
            return prefix + f"цена проставлена при подготовке датасета, у {first_name} — нет"
        return prefix + f"у {first_name} цена проставлена при подготовке датасета, здесь — нет"
    if key == "city_imputed_penalty":
        if value < first_value:
            return prefix + f"город проставлен при подготовке датасета, у {first_name} — нет"
        return prefix + f"у {first_name} город проставлен при подготовке датасета, здесь — нет"
    if key == "price_fit":
        return prefix + (
            f"балл за соответствие цены бюджету {value} против {first_value} у {first_name}"
        )
    if key == "hours_headroom":
        return prefix + (
            f"балл за запас по часам {value} против {first_value} у {first_name}"
        )
    if key == "format_mentioned_in_description":
        this_count = _format_mention_count(profile, query)
        first_count = _format_mention_count(first_profile, query)
        return prefix + (
            f"в описании {this_count} основ формата «{query.get('event_type', '')}», "
            f"у {first_name} — {first_count}"
        )
    label = SCORE_PART_LABELS.get(key, key)
    return prefix + f"балл за {label}: {value} против {first_value} у {first_name}"


def _make_card(
    profile: dict[str, Any], query: dict[str, Any], position: int,
    first_profile: dict[str, Any],
) -> dict[str, Any]:
    busy_dates = _as_values(profile.get("busy_dates"))
    requested_date = str(query["date"])
    if busy_dates:
        availability = f"Свободен(на) {requested_date} по календарю профиля"
    else:
        availability = f"Дата {requested_date} не отмечена как занятая; календарь профиля пуст"

    notes: list[str] = []
    if _as_bool(profile.get("synthetic", False)):
        notes.append("Синтетический профиль")
    if _as_bool(profile.get("city_imputed", False)):
        notes.append("Город восстановлен при подготовке датасета")
    if _as_bool(profile.get("price_imputed", False)):
        notes.append("Цена восстановлена при подготовке датасета")

    return {
        "id": profile.get("id"),
        "name": profile.get("anon_name") or profile.get("name") or "Без имени",
        "categories": profile.get("categories") or [],
        "city": profile.get("city") or "",
        "price": profile.get("price_from_kzt"),
        "synthetic": _as_bool(profile.get("synthetic", False)),
        "price_imputed": _as_bool(profile.get("price_imputed", False)),
        "city_imputed": _as_bool(profile.get("city_imputed", False)),
        "score": profile["score"],
        "score_parts": profile["score_parts"],
        "explanation": explain_profile(profile, query),
        "availability": availability,
        "notes": notes,
        "distinctive": profile.get("distinctive", ""),
        "rank_reason": _rank_reason(position, profile, first_profile, query),
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
    funnel = _funnel(query, filtered)

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
        selected = [dict(profile) for profile in ranked[:MAX_CARDS]]
        distinctives = _distinctive_profiles(selected, query)
        for profile, distinctive in zip(selected, distinctives):
            profile["distinctive"] = distinctive
        first_profile = selected[0]
        cards = [
            _make_card(profile, query, position, first_profile)
            for position, profile in enumerate(selected, start=1)
        ]
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
        "funnel": funnel,
    }
