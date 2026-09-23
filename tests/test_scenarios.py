"""Print the six hackathon scenarios and check deterministic output."""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from pipeline.recommend import recommend


SCENARIOS: list[dict[str, Any]] = [
    {
        "city": "Алматы",
        "date": "2026-10-07",
        "event_type": "свадьба",
        "category": "Ведущий",
        "budget": 1_200_000,
        "hours": 5,
        "language": None,
    },
    {
        "city": "Алматы",
        "date": "2026-10-09",
        "event_type": "свадьба",
        "category": "Ведущий",
        "budget": 1_200_000,
        "hours": 5,
        "language": None,
    },
    {
        "city": "Алматы",
        "date": "2026-10-10",
        "event_type": "свадьба",
        "category": "Флорист",
        "budget": 400_000,
        "hours": None,
        "language": None,
    },
    {
        "city": "Астана",
        "date": "2026-10-10",
        "event_type": "корпоратив",
        "category": "Лайв-бэнд",
        "budget": 1_000_000,
        "hours": None,
        "language": None,
    },
    {
        "city": "Алматы",
        "date": "2026-12-26",
        "event_type": "корпоратив",
        "category": "Ведущий",
        "budget": 300_000,
        "hours": None,
        "language": None,
    },
    {
        "city": "Шымкент",
        "date": "2026-10-10",
        "event_type": "свадьба",
        "category": "Фотограф",
        "budget": 500_000,
        "hours": None,
        "language": None,
    },
]


def _print_scenario(number: int, query: dict[str, Any], result: dict[str, Any]) -> None:
    print(f"\nСценарий {number}: {query}")
    print(f"outcome: {result['outcome']}")
    print(f"headline: {result['headline']}")
    print(f"summary: {result['summary']}")
    print("funnel:")
    for step in result["funnel"]:
        print(f"  - {step['step']}: {step['count']}")

    print("Карточки:")
    if result["cards"]:
        for card in result["cards"]:
            print(f"  - {card['name']} — балл {card['score']}")
            print(f"      score_parts: {card['score_parts']}")
            print(f"      distinctive: {card['distinctive']}")
            print(f"      rank_reason: {card['rank_reason']}")
            print(f"      price_imputed: {card['price_imputed']}")
            print(f"      city_imputed: {card['city_imputed']}")
            print(f"      synthetic: {card['synthetic']}")
            print(f"      explanation: {card['explanation']}")
            print(f"      availability: {card['availability']}")
            print(f"      notes: {card['notes']}")
    else:
        print("  (нет)")

    print("Первые 3 отказа:")
    rejected = result["rejected"][:3]
    if rejected:
        for profile in rejected:
            reasons = "; ".join(
                reason["text"] for reason in profile.get("reasons", [])
            )
            print(f"  - {profile.get('name') or profile.get('id')}: {reasons}")
    else:
        print("  (нет)")


def main() -> None:
    results = []
    for number, query in enumerate(SCENARIOS, start=1):
        result = recommend(query)
        results.append(result)
        _print_scenario(number, query, result)

    repeated_first_result = recommend(SCENARIOS[0])
    print(f"\nДетерминизм первого запроса: {results[0] == repeated_first_result}")


if __name__ == "__main__":
    main()
