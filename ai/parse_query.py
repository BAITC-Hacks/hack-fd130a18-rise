"""Mock extraction of search parameters from free-form user text."""

from pydantic import BaseModel, Field


class ParsedQuery(BaseModel):
    language: str | None = Field(default=None, description="Язык проведения")
    event_type: str | None = Field(default=None, description="Тип мероприятия")
    date: str | None = Field(default=None, description="Дата проведения")
    budget: int | None = Field(default=None, description="Бюджет в тенге")


async def parse_user_query(text: str) -> ParsedQuery:
    """Return fixed values until free-text parsing is implemented."""
    return ParsedQuery(
        language="kz",
        event_type="той",
        date="2026-11-14",
        budget=800000,
    )
