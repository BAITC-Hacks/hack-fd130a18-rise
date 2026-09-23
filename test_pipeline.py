"""Run focused checks for guardrails, embedding ranking, and agent filters."""

from __future__ import annotations

import asyncio
from time import perf_counter

from ai.parse_query import ParsedQuery
from pipeline.agent_filters import apply_agent_filters
from pipeline.guardrails import get_safe_explanation, get_template_explanation
from pipeline.ranking import rank_cards_by_embedding


def report(name: str, started_at: float) -> None:
    print(f"[OK] {name} — {perf_counter() - started_at:.2f} с")


async def check_guardrails_cache() -> None:
    started_at = perf_counter()
    facts = {"name": "Card A", "price": 800_000, "score": 90}
    calls = 0

    async def first_llm(source_facts: dict) -> str:
        nonlocal calls
        calls += 1
        return "Card A: цена 800000 ₸, балл 90."

    async def should_not_be_called(source_facts: dict) -> str:
        nonlocal calls
        calls += 1
        raise AssertionError("LLM вызвана повторно вместо использования кэша")

    first = await get_safe_explanation("test-cache-card", facts, first_llm)
    second = await get_safe_explanation("test-cache-card", facts, should_not_be_called)
    assert first == "Card A: цена 800000 ₸, балл 90."
    assert second == first
    assert calls == 1
    report("Guardrails: кэширование", started_at)


async def check_guardrails_numbers() -> None:
    started_at = perf_counter()
    facts = {"name": "Card B", "price": 750_000, "score": 82}

    async def missing_price(source_facts: dict) -> str:
        return "Card B: балл 82."

    result = await get_safe_explanation("test-missing-price-card", facts, missing_price)
    assert result == get_template_explanation(facts)
    report("Guardrails: пропущенная цена отклонена", started_at)


async def check_guardrails_timeout() -> None:
    started_at = perf_counter()
    facts = {"name": "Card C", "price": 600_000, "score": 75}

    async def slow_llm(source_facts: dict) -> str:
        await asyncio.sleep(6)
        return "Card C: цена 600000 ₸, балл 75."

    result = await get_safe_explanation("test-timeout-card", facts, slow_llm)
    elapsed = perf_counter() - started_at
    assert result == get_template_explanation(facts)
    assert 4.5 <= elapsed < 6.0, f"Ожидался таймаут около 5 с, получено {elapsed:.2f} с"
    report("Guardrails: таймаут и шаблонный ответ", started_at)


def check_embedding_ranking() -> None:
    started_at = perf_counter()
    query_vector = [1.0, 0.0, 0.0]
    cards_embeddings = {
        "Card A": [0.9, 0.1, 0.0],
        "Card B": [0.5, 0.5, 0.0],
        "Card C": [0.0, 1.0, 0.0],
    }

    ranked = rank_cards_by_embedding(query_vector, cards_embeddings)
    assert [card_id for card_id, _ in ranked] == ["Card A", "Card B", "Card C"]
    assert ranked[0][1] > ranked[1][1] > ranked[2][1]
    report("Векторное ранжирование: A → B → C", started_at)


def check_agent_filters() -> None:
    started_at = perf_counter()
    parsed_query = ParsedQuery(language="kz", budget=800_000)
    cards = [
        {"id": "Card A", "language": "kz", "price": 700_000},
        {"id": "Card B", "language": "kz", "price": 900_000},
        {"id": "Card C", "language": "ru", "price": 600_000},
    ]

    filtered = apply_agent_filters(cards, parsed_query)
    assert [card["id"] for card in filtered] == ["Card A"]
    report("Агентская фильтрация: осталась Card A", started_at)


async def main() -> None:
    overall_started_at = perf_counter()
    await check_guardrails_cache()
    await check_guardrails_numbers()
    await check_guardrails_timeout()
    check_embedding_ranking()
    check_agent_filters()
    print(f"Все проверки пройдены за {perf_counter() - overall_started_at:.2f} с")


if __name__ == "__main__":
    asyncio.run(main())
