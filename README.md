# 🎯 EventMatch AI (#79-lite)

Сервис умного подбора event-подрядчиков в Казахстане с честной фильтрацией по календарю/бюджету, векторным ранжированием и AI-объяснениями.

## 💡 Пайплайн

1. **Agentic AI Parsing (`ai/parse_query.py`):** Извлечение параметров из текста.
2. **Hard Filtering (`pipeline/filter.py`):** Фильтрация по календарю (`busy_dates`), городу и бюджету.
3. **Semantic Ranking (`pipeline/ranking.py`):** Векторный поиск по эмбеддингам OpenAI.
4. **LLM Polish & Explain (`ai/polish.py`):** Генерация уникальных объяснений с детерминированным фолбэком.

## 🚀 Быстрый запуск

1. Установка: `pip install -r requirements.txt`
2. Переменные: Создать `.env` с `OPENAI_API_KEY=your_key`
3. Эмбеддинги: `python scripts/generate_embeddings.py`
4. UI: `streamlit run ui/app.py`

## 🧪 Демо-сценарии

- **Плотная категория:** Ведущий в Алматы на 14 ноября
- **Редкая категория:** Флорист в Астане
- **Нулевой результат:** Банкетный зал в Алматы на 20 декабря (бюджет 100k ₸)
