"""
Заглушка для интерфейса, пока воронка лидера не готова.

mock_recommend(query) возвращает результат строго в формате лидера:
    result = {outcome, headline, summary, cards, rejected}
Имена, цены и цифры здесь придуманы. Когда появится pipeline/recommend.py,
app.py автоматически начнёт вызывать настоящую функцию, а этот файл станет не нужен.

Какие ответы даёт заглушка (удобно для проверки всех экранов):
    • категория «Инструменталист» в Астане      → no_category
    • дата с 20 по 31 декабря                   → none_passed
    • категория «Флорист»                       → matched, 1 карточка
    • 28 ноября                                 → matched, другой состав (проверка баннера «изменилось из-за даты»)
    • всё остальное                             → matched, 3 карточки
"""

from datetime import date


def _card(cid, name, category, city, price, explanation, availability, notes,
          score, score_parts, synthetic=False, price_imputed=False):
    return {
        "id": cid,
        "name": name,
        "categories": [category],
        "city": city,
        "price": price,
        "synthetic": synthetic,
        "price_imputed": price_imputed,        # необязательное поле (просим лидера добавить)
        "score": score,
        "score_parts": score_parts,
        "explanation": explanation,
        "availability": availability,
        "notes": notes,
    }


def mock_recommend(query: dict) -> dict:
    city = query.get("city") or "Астана"
    category = query.get("category") or "Ведущий"
    day = date.fromisoformat(query["date"])
    budget = query.get("budget") or 0
    date_text = f"{day.day:02d}.{day.month:02d}"

    # --- исход 1: такой категории в городе нет
    if category == "Инструменталист" and city == "Астана":
        return {
            "outcome": "no_category",
            "headline": "В Астане нет инструменталистов в каталоге",
            "summary": "В каталоге 3 инструменталиста, и все работают в Алматы. "
                       "Дело не в дате и не в бюджете — в Астане профилей этой категории просто нет.",
            "cards": [],
            "rejected": [],
        }

    # --- исход 2: кандидаты есть, но никто не прошёл
    if day.month == 12 and day.day >= 20:
        return {
            "outcome": "none_passed",
            "headline": f"На {date_text} подходящих вариантов нет",
            "summary": f"В городе {city} 8 кандидатов в категории «{category}». "
                       f"5 заняты {date_text}, 1 не берёт этот формат, 2 свободны, но дороже бюджета.",
            "cards": [],
            "rejected": [
                {"id": "r1", "name": "Нур Холл", "reasons": [{"code": "budget", "text": "от 1 200 000 ₸ — дороже бюджета"}]},
                {"id": "r2", "name": "Алтын Сарай", "reasons": [{"code": "budget", "text": "от 1 450 000 ₸ — дороже бюджета"}]},
                {"id": "r3", "name": "Жұлдыз", "reasons": [{"code": "busy", "text": f"занят {date_text}"}]},
                {"id": "r4", "name": "Шаңырақ", "reasons": [{"code": "busy", "text": f"занят {date_text}"},
                                                            {"code": "format", "text": "не берёт этот формат"}]},
            ],
            "funnel": [  # необязательное поле (просим лидера добавить)
                {"label": f"{category}: {city}", "count": 8},
                {"label": "Берут этот формат", "count": 7},
                {"label": f"Свободны {date_text}", "count": 2},
                {"label": "В бюджете", "count": 0},
            ],
        }

    # --- редкая категория: меньше трёх
    if category == "Флорист":
        return {
            "outcome": "matched",
            "headline": "Нашли 1 из 3",
            "summary": f"Во всём каталоге флористов трое: один работает в Алматы, второй в Астане занят {date_text}. "
                       "Подходит один — показываем его, а не добираем до трёх.",
            "cards": [
                _card("f1", "Сауле Ж.", category, city, 120000,
                      f"Единственный свободный флорист города на {date_text}. Остаётся {budget - 120000:,} ₸ запаса. "
                      "В описании — оформление арки и столов гостей живыми сезонными цветами.".replace(",", " "),
                      f"Свободна {date_text}", ["Берёт этот формат", "Часы не требуются"],
                      0.61, {"формат": 0.45, "бюджет": 0.16, "часы": 0.0}),
            ],
            "rejected": [
                {"id": "f2", "name": "Мадина Р.", "reasons": [{"code": "busy", "text": f"занята {date_text}"}]},
                {"id": "f3", "name": "Гүлнар А.", "reasons": [{"code": "city", "text": "работает в Алматы"}]},
            ],
        }

    # --- обычный исход: три карточки
    aidana = _card("h1", "Айдана С.", category, city, 350000,
                   "Единственная из трёх ведёт весь вечер на казахском, а не вставками: в описании — узату и беташар. "
                   "Запас бюджета 50 000 ₸.",
                   f"Свободна {date_text}", ["Казахский — основной", "До 6 ч"],
                   0.53, {"формат": 0.45, "бюджет": 0.04, "часы": 0.04})
    marat = _card("h2", "Марат К.", category, city, 280000,
                  "Самый доступный из трёх: остаётся 120 000 ₸ на другие расходы. "
                  "Акцент на камерных свадьбах до 80 гостей.",
                  f"Свободен {date_text}", ["Казахский и русский", "До 5 ч"],
                  0.49, {"формат": 0.40, "бюджет": 0.09, "часы": 0.0}, synthetic=True)
    erlan = _card("h3", "Ерлан Б.", category, city, 390000,
                  "Больше всех запас по времени — до 8 ч, если программа затянется. "
                  "Бюджет впритык, цена в каталоге оценочная.",
                  f"Свободен {date_text}", ["Казахский и русский", "До 8 ч"],
                  0.48, {"формат": 0.35, "бюджет": 0.01, "часы": 0.12}, price_imputed=True)
    dina = _card("h4", "Дина М.", category, city, 370000,
                 "Лучше всех подходит под формат по описанию — отдельно упоминает программу для детей-гостей. "
                 "Ведёт на казахском и русском.",
                 f"Свободна {date_text}", ["Казахский и русский", "До 6 ч"],
                 0.50, {"формат": 0.44, "бюджет": 0.02, "часы": 0.04})

    if day == date(2026, 11, 28):
        cards = [dina, marat, erlan]
        rejected = [
            {"id": "h1", "name": "Айдана С.", "reasons": [{"code": "busy", "text": f"занята {date_text}"}]},
            {"id": "h5", "name": "Руслан Т.", "reasons": [{"code": "budget", "text": "дороже бюджета на 50 000 ₸"}]},
        ]
    else:
        cards = [aidana, marat, erlan]
        rejected = [
            {"id": "h4", "name": "Дина М.", "reasons": [{"code": "busy", "text": f"занята {date_text}"}]},
            {"id": "h5", "name": "Руслан Т.", "reasons": [{"code": "budget", "text": "дороже бюджета на 50 000 ₸"}]},
        ]

    return {
        "outcome": "matched",
        "headline": "Подобрали 3 варианта",
        "summary": f"Из 15 кандидатов в категории «{category}» в городе {city} все условия прошли трое.",
        "cards": cards,
        "rejected": rejected,
        "funnel": [
            {"label": f"{category}: {city}", "count": 15},
            {"label": "Берут этот формат", "count": 13},
            {"label": f"Свободны {date_text}", "count": 9},
            {"label": "В бюджете", "count": 6},
            {"label": "Язык", "count": 4},
            {"label": "Часы", "count": 3},
        ],
    }
