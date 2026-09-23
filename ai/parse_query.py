import os
from typing import Optional
from pydantic import BaseModel, Field
from openai import AsyncOpenAI

client = AsyncOpenAI(api_key=os.getenv("OPENAI_API_KEY", "your-api-key"))

# Схема данных для фильтров
class ParsedQueryParams(BaseModel):
    category_or_role: Optional[str] = Field(None, description="Категория/профессия, например: 'ведущий', 'диджей', 'фотограф'")
    language: Optional[str] = Field(None, description="Язык проведения мероприятия, например: 'казахский', 'русский', 'двуязычный'")
    event_type: Optional[str] = Field(None, description="Тип мероприятия, например: 'той', 'свадьба', 'корпоратив'")
    date: Optional[str] = Field(None, description="Дата в формате YYYY-MM-DD или свободном описании")
    budget_kzt: Optional[int] = Field(None, description="Максимальный бюджет в тенге (число без пробелов)")

PARSE_SYSTEM_PROMPT = """\
Ты — интеллектуальный ассистент поиска услуг. Твоя задача — проанализировать запрос пользователя и извлечь структурированные параметры для фильтрации воронки.

Извлекай строго только те параметры, которые явно указаны или прямо подразумеваются в тексте.
Если параметр не упомянут, оставляй null.
"""

async def parse_user_query(user_text: str) -> ParsedQueryParams:
    """
    Извлекает параметры из свободной речи пользователя.
    """
    response = await client.beta.chat.completions.parse(
        model="gpt-4o-mini",
        temperature=0.0,
        messages=[
            {"role": "system", "content": PARSE_SYSTEM_PROMPT},
            {"role": "user", "content": user_text}
        ],
        response_format=ParsedQueryParams
    )
    
    return response.choices[0].message.parsed