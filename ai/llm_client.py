"""OpenAI configuration and safe error messages for the application."""

import os
from pathlib import Path

from dotenv import dotenv_values
from openai import AsyncOpenAI

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_MODEL = "gpt-4o-mini"


def settings() -> dict:
    # Read on each request so an edited .env does not require restarting Python.
    values = dotenv_values(ROOT / ".env")
    return {
        "api_key": os.environ.get("OPENAI_API_KEY") or values.get("OPENAI_API_KEY"),
        "model": os.environ.get("OPENAI_MODEL") or values.get("OPENAI_MODEL") or DEFAULT_MODEL,
    }


def create_client(timeout: float = 5.0) -> AsyncOpenAI:
    config = settings()
    if not config["api_key"] or config["api_key"] == "your-api-key":
        raise ValueError("Добавьте OPENAI_API_KEY в .env в корне проекта.")
    return AsyncOpenAI(api_key=config["api_key"], timeout=timeout, max_retries=0)


def error_message(error: Exception) -> str:
    """Never expose SDK responses, request headers, or credentials in the UI."""
    status = getattr(error, "status_code", None)
    if status == 401:
        return "OpenAI отклонил ключ. Проверьте OPENAI_API_KEY в .env."
    if status == 429:
        return "OpenAI сообщил об ограничении запросов или квоты. Проверьте баланс API и лимиты проекта."
    if status in (403, 404):
        return "Нет доступа к модели OpenAI. Проверьте права ключа и OPENAI_MODEL."
    if isinstance(error, TimeoutError) or type(error).__name__ == "APITimeoutError":
        return "OpenAI не ответил вовремя. Попробуйте ещё раз."
    if type(error).__name__ == "APIConnectionError":
        return "Не удалось соединиться с OpenAI. Проверьте подключение к интернету."
    return "Не удалось получить ответ OpenAI. Можно продолжить через форму."


async def get_llm_completion(
    system_prompt: str, user_prompt: str,
    model: str | None = None, temperature: float = 0.0,
) -> str:
    async with create_client(timeout=4.5) as client:
        response = await client.chat.completions.create(
            model=model or settings()["model"], temperature=temperature,
            max_completion_tokens=1000, store=False,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
        )
    message = response.choices[0].message
    if message.refusal or not message.content or response.choices[0].finish_reason != "stop":
        raise ValueError("Модель не вернула полный текст.")
    return message.content.strip()
