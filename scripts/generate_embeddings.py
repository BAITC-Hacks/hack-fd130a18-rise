import os
import json
import asyncio
from openai import AsyncOpenAI

client = AsyncOpenAI(api_key=os.getenv("OPENAI_API_KEY", "your-api-key"))

EMBEDDING_MODEL = "text-embedding-3-small"

async def get_embedding(text: str) -> list[float]:
    """Получение вектора для одного текста."""
    response = await client.embeddings.create(
        input=text,
        model=EMBEDDING_MODEL
    )
    return response.data[0].embedding

async def build_embeddings_store(cards: list[dict], output_file: str = "data/embeddings.json"):
    """
    Принимает список карточек, считает вектор для каждой и сохраняет в JSON.
    """
    embeddings_map = {}
    
    print(f"Обработка {len(cards)} карточек...")
    for card in cards:
        card_id = str(card["id"])
        text_to_embed = f"{card.get('title', '')}. {card.get('description', '')}".strip()
        
        vector = await get_embedding(text_to_embed)
        embeddings_map[card_id] = vector
        print(f" Готово: {card_id}")
    
    os.makedirs(os.path.dirname(output_file), exist_ok=True)
    
    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(embeddings_map, f, ensure_ascii=False, indent=2)
        
    print(f"\n Все эмбеддинги сохранены в {output_file}")

if __name__ == "__main__":
    mock_cards = [
        {"id": "card_1", "title": "Ведущий Аскар", "description": "Опытный тамада на казахском и русском языках, проводит тои и свадебные мероприятия."},
        {"id": "card_2", "title": "DJ Alex", "description": "Профессиональный диджей со своим звуковым оборудованием, коммерческая музыка и хит-парады."},
        {"id": "card_3", "title": "Шоу балет Ару", "description": "Танцевальный коллектив для национальных праздников, тоев и корпоративов."}
    ]
    
    asyncio.run(build_embeddings_store(mock_cards))
    