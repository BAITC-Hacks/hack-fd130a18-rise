import json
from ai.llm_client import get_llm_completion

POLISH_SYSTEM_PROMPT = """\
Ты — копирайтер сервис-агрегатора. Твоя задача: переписать сухое описание карточки исполнителя/услуги в яркий, живой и убедительный текст.

СТРОГИЕ ПРАВИЛА:
1. Сохраняй абсолютно ВСЕ цифры, суммы, даты, проценты и показатели из исходных фактов БЕЗ ИЗМЕНЕНИЙ (например: 800 000, 14 ноября, 10 лет, 4.9).
2. Не выдумывай новые факты, которых нет в исходных данных.
3. Текст должен быть естественным, грамотным и привлекательным для клиента.
4. Возвращай ТОЛЬКО итоговый текст, без раскладок, комментариев и кавычек.
"""

async def generate_polished_text(card_facts: dict) -> str:
    """
    Принимает словарь с фактами карточки, возвращает улучшенный текст.
    """
    user_prompt = f"Вот сухие факты карточки:\n{json.dumps(card_facts, ensure_ascii=False, indent=2)}\n\nНапиши живое и привлекательное описание."
    
    polished_text = await get_llm_completion(
        system_prompt=POLISH_SYSTEM_PROMPT,
        user_prompt=user_prompt,
        temperature=0.0
    )
    return polished_text
    