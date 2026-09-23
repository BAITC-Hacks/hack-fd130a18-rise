import os
from openai import AsyncOpenAI

# Инициализируем клиента ИИ
client = AsyncOpenAI(api_key=os.getenv("OPENAI_API_KEY", "your-api-key"))

DEFAULT_MODEL = "gpt-4o-mini"

async def get_llm_completion(
    system_prompt: str, 
    user_prompt: str, 
    model: str = DEFAULT_MODEL, 
    temperature: float = 0.0
) -> str:
    """Отправляет запрос к ИИ и возвращает ответ."""
    response = await client.chat.completions.create(
        model=model,
        temperature=temperature,
        seed=42,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ]
    )
    return response.choices[0].message.content.strip()
