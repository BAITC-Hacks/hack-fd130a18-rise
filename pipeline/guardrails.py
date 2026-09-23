"""Validate LLM explanations against the facts of a contractor card."""

from __future__ import annotations

import asyncio
import re
from typing import Any, Awaitable, Callable


_EXPLANATION_CACHE: dict[str, str] = {}


def extract_numbers(data: dict) -> set[str]:
    """Extract every digit sequence from the source facts."""
    return set(re.findall(r"\d+", str(data)))


def validate_numbers(facts: dict, generated_text: str) -> bool:
    """Require every number in the facts to occur in the generated text."""
    generated_numbers = set(re.findall(r"\d+", generated_text))
    return extract_numbers(facts).issubset(generated_numbers)


def get_template_explanation(facts: dict) -> str:
    """Return a factual fallback with name, price, and score."""
    name = facts.get("name") or facts.get("title") or "Подрядчик"
    price = facts.get("price")
    score = facts.get("score", facts.get("rating"))

    price_text = f"{price} ₸" if price is not None else "не указана"
    score_text = str(score) if score is not None else "не указан"
    return f"{name}. Цена: {price_text}. Рейтинг: {score_text}."


async def get_safe_explanation(
    card_id: str,
    facts: dict,
    llm_func: Callable[[dict], Awaitable[str]],
) -> str:
    """Return a validated LLM explanation or a deterministic fallback."""
    if card_id in _EXPLANATION_CACHE:
        return _EXPLANATION_CACHE[card_id]

    try:
        generated_text = await asyncio.wait_for(llm_func(facts), timeout=5)
        if validate_numbers(facts, generated_text):
            _EXPLANATION_CACHE[card_id] = generated_text
            return generated_text
    except Exception:
        pass

    return get_template_explanation(facts)
