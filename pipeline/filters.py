"""Apply deterministic, rule-based filters to contractor profiles."""

from __future__ import annotations

from collections import Counter
from datetime import date
from typing import Any, Iterable


def _normalized(value: Any) -> str:
    """Normalize text for case-insensitive exact matching."""
    return str(value or "").strip().casefold()


def _as_values(value: Any) -> list[str]:
    """Accept either the normalized list from load.py or a pipe string."""
    if value is None:
        return []
    if isinstance(value, str):
        return [part.strip() for part in value.split("|") if part.strip()]
    if isinstance(value, Iterable):
        return [str(part).strip() for part in value if str(part).strip()]
    return [str(value).strip()]


def _validate_query(query: dict[str, Any]) -> None:
    required = ("city", "date", "event_type", "category", "budget")
    missing = [key for key in required if key not in query or query[key] is None]
    if missing:
        raise ValueError("В запросе не заполнены поля: " + ", ".join(missing))

    try:
        date.fromisoformat(str(query["date"]))
    except (TypeError, ValueError) as error:
        raise ValueError(
            "Поле date должно быть датой в формате ГГГГ-ММ-ДД."
        ) from error

    try:
        budget = int(query["budget"])
    except (TypeError, ValueError) as error:
        raise ValueError("Поле budget должно быть целым числом в тенге.") from error
    if budget < 0:
        raise ValueError("Поле budget не может быть отрицательным.")

    if query.get("hours") is not None:
        try:
            hours = float(query["hours"])
        except (TypeError, ValueError) as error:
            raise ValueError("Поле hours должно быть числом или None.") from error
        if hours <= 0:
            raise ValueError("Поле hours должно быть больше нуля.")


def _reason(code: str, text: str) -> dict[str, str]:
    return {"code": code, "text": text}


def filter_profiles(
    profiles: Iterable[dict[str, Any]], query: dict[str, Any]
) -> dict[str, Any]:
    """Filter profiles and report every hard-filter reason for each rejection.

    A profile is first considered a category candidate when its city and one
    of its categories exactly match the request, ignoring letter case and
    surrounding whitespace. Hard filters are then applied to those candidates.

    The returned intermediate result contains ``outcome`` (``no_category``,
    ``matched``, or ``none_passed``), ``category_profiles``, ``passed``,
    ``rejected``, and counts. ``rejected`` entries use the agreed ``id``,
    ``name``, ``reasons`` shape. The final cards and headline are assembled
    later by recommend.py.
    """
    _validate_query(query)
    profiles = list(profiles)

    requested_city = _normalized(query["city"])
    requested_category = _normalized(query["category"])
    requested_format = _normalized(query["event_type"])
    requested_language = _normalized(query.get("language"))
    requested_date = str(query["date"]).strip()
    budget = int(query["budget"])
    requested_hours = (
        float(query["hours"]) if query.get("hours") is not None else None
    )

    category_profiles = [
        profile
        for profile in profiles
        if _normalized(profile.get("city")) == requested_city
        and any(
            _normalized(category) == requested_category
            for category in _as_values(profile.get("categories"))
        )
    ]

    if not category_profiles:
        outcome = "no_category"
        passed: list[dict[str, Any]] = []
        rejected: list[dict[str, Any]] = []
        rejection_counts: dict[str, int] = {}
    else:
        passed = []
        rejected = []
        reason_totals: Counter[str] = Counter()

        for profile in category_profiles:
            reasons: list[dict[str, str]] = []
            name = str(profile.get("anon_name") or profile.get("name") or "")

            if requested_date in _as_values(profile.get("busy_dates")):
                reasons.append(
                    _reason(
                        "busy_date",
                        f"Занят(а) {requested_date} и недоступен(на) в эту дату.",
                    )
                )

            price = profile.get("price_from_kzt")
            if price is None or str(price).strip() == "":
                reasons.append(
                    _reason(
                        "price_unknown",
                        "В профиле не указана цена, поэтому нельзя проверить бюджет.",
                    )
                )
            else:
                try:
                    price_value = int(price)
                except (TypeError, ValueError):
                    reasons.append(
                        _reason(
                            "price_unknown",
                            "Цена в профиле указана некорректно, поэтому бюджет нельзя проверить.",
                        )
                    )
                else:
                    if price_value > budget:
                        reasons.append(
                            _reason(
                                "over_budget",
                                f"Цена от {price_value:,} ₸ выше бюджета {budget:,} ₸.".replace(
                                    ",", " "
                                ),
                            )
                        )

            formats = _as_values(profile.get("event_formats"))
            if requested_format and not any(
                _normalized(event_format) == requested_format
                for event_format in formats
            ):
                reasons.append(
                    _reason(
                        "format_mismatch",
                        f"В профиле не указан формат «{query['event_type']}».",
                    )
                )

            if requested_language:
                languages = _as_values(profile.get("languages"))
                if not any(
                    _normalized(language) == requested_language
                    for language in languages
                ):
                    shown_languages = ", ".join(languages) if languages else "не указаны"
                    reasons.append(
                        _reason(
                            "language_mismatch",
                            f"Запрошен язык «{query['language']}», в профиле: {shown_languages}.",
                        )
                    )

            if requested_hours is not None:
                max_hours = profile.get("max_hours")
                if max_hours is not None and str(max_hours).strip() != "":
                    try:
                        max_hours_value = float(max_hours)
                    except (TypeError, ValueError):
                        reasons.append(
                            _reason(
                                "hours_unknown",
                                "Ограничение по длительности в профиле указано некорректно.",
                            )
                        )
                    else:
                        if requested_hours > max_hours_value:
                            reasons.append(
                                _reason(
                                    "hours_exceeded",
                                    f"Запрошено {requested_hours:g} ч., максимум подрядчика — {max_hours_value:g} ч.",
                                )
                            )

            if reasons:
                rejected.append(
                    {"id": profile.get("id"), "name": name, "reasons": reasons}
                )
                reason_totals.update(reason["code"] for reason in reasons)
            else:
                passed.append(profile)

        rejection_counts = dict(sorted(reason_totals.items()))
        outcome = "matched" if passed else "none_passed"

    return {
        "outcome": outcome,
        "category_profiles": category_profiles,
        "category_count": len(category_profiles),
        "passed": passed,
        "passed_count": len(passed),
        "rejected": rejected,
        "rejected_count": len(rejected),
        "rejection_counts": rejection_counts,
    }
