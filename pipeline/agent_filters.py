"""Apply parsed free-text search constraints to an existing card list."""

from __future__ import annotations

from typing import Any

from ai.parse_query import ParsedQuery


LANGUAGE_ALIASES = {
    "kz": "казахский",
    "kk": "казахский",
    "қазақша": "казахский",
    "ru": "русский",
    "рус": "русский",
    "en": "английский",
    "eng": "английский",
}


def _values(value: Any) -> list[str]:
    """Read one value, a list, or values separated by a pipe."""
    if value is None:
        return []
    if isinstance(value, str):
        return [part.strip() for part in value.split("|") if part.strip()]
    if isinstance(value, (list, tuple, set)):
        return [str(part).strip() for part in value if str(part).strip()]
    return [str(value).strip()]


def _language(value: str) -> str:
    normalized = value.strip().casefold()
    return LANGUAGE_ALIASES.get(normalized, normalized)


def apply_agent_filters(cards: list[dict], parsed_query: ParsedQuery) -> list[dict]:
    """Keep cards matching the parsed parameters, preserving their order.

    Card fields may use ``language``/``event_type``/``price`` or the dataset's
    ``languages``/``event_formats``/``price_from_kzt`` names. If a card has an
    ``available_dates`` or ``busy_dates`` calendar, the parsed date is checked
    against that calendar too. A card without either calendar is assumed to
    have passed the existing availability filter upstream.
    """
    selected: list[dict] = []
    requested_language = (
        _language(parsed_query.language) if parsed_query.language else None
    )
    requested_event_type = (
        parsed_query.event_type.strip().casefold()
        if parsed_query.event_type
        else None
    )

    for card in cards:
        if requested_language:
            card_languages = _values(card.get("languages", card.get("language")))
            if requested_language not in {_language(value) for value in card_languages}:
                continue

        if parsed_query.budget is not None:
            price = card.get("price", card.get("price_from_kzt"))
            try:
                if price is None or float(price) > parsed_query.budget:
                    continue
            except (TypeError, ValueError):
                continue

        if requested_event_type:
            card_event_types = _values(
                card.get("event_formats", card.get("event_type"))
            )
            if requested_event_type not in {
                value.casefold() for value in card_event_types
            }:
                continue

        if parsed_query.date:
            if "available_dates" in card:
                if parsed_query.date not in _values(card["available_dates"]):
                    continue
            elif "busy_dates" in card:
                if parsed_query.date in _values(card["busy_dates"]):
                    continue

        selected.append(card)

    return selected


if __name__ == "__main__":
    example_cards = [
        {
            "id": "A",
            "language": "kz",
            "event_type": "той",
            "price": 700_000,
            "available_dates": ["2026-11-14"],
        },
        {
            "id": "B",
            "language": "ru",
            "event_type": "той",
            "price": 600_000,
            "available_dates": ["2026-11-14"],
        },
        {
            "id": "C",
            "language": "kz",
            "event_type": "той",
            "price": 900_000,
            "available_dates": ["2026-11-14"],
        },
        {
            "id": "D",
            "language": "kz",
            "event_type": "свадьба",
            "price": 500_000,
            "available_dates": ["2026-11-14"],
        },
        {
            "id": "E",
            "language": "kz",
            "event_type": "той",
            "price": 750_000,
            "available_dates": ["2026-11-15"],
        },
    ]
    example_query = ParsedQuery(
        language="kz",
        event_type="той",
        date="2026-11-14",
        budget=800_000,
    )
    print(apply_agent_filters(example_cards, example_query))
