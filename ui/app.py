"""
TAŃDA — интерфейс подбора подрядчиков (Streamlit).

Запуск из корня проекта:
    streamlit run ui/app.py

Интерфейс не содержит логики подбора. Он собирает параметры формы,
вызывает recommend(query) из pipeline/recommend.py (зона лидера)
и рисует результат. Пока pipeline/recommend.py не готов, работает
заглушка ui/mock_data.py — на экране будет пометка «Демо-данные».

Контракт с лидером (не меняется):
    query  = {city, date "ГГГГ-ММ-ДД", event_type, category, budget, hours или None, language или None}
    result = {outcome: "matched" | "no_category" | "none_passed",
              headline, summary,
              cards: [{id, name, categories, city, price, synthetic, score, score_parts,
                       explanation, availability, notes}],
              rejected: [{id, name, reasons: [{code, text}]}]}
Необязательные поля, которые интерфейс покажет, если они появятся:
    cards[].price_imputed, cards[].city_imputed, cards[].facts, result.funnel,
    result.suggestions, result.season_note, result.meta
"""

import asyncio
import csv
import html
import sys
import time
from datetime import date
from pathlib import Path

import streamlit as st

# ---------------------------------------------------------------- пути и источник данных
UI_DIR = Path(__file__).resolve().parent
ROOT = UI_DIR.parent
for p in (str(ROOT), str(UI_DIR)):
    if p not in sys.path:
        sys.path.insert(0, p)

from ai.parse_query import parse_user_query
from ai.llm_client import error_message
from ai.polish import polish_result

IMPORT_NOTE = ""
try:
    from pipeline.recommend import recommend  # функция лидера
    DATA_SOURCE = "pipeline"
except ModuleNotFoundError as err:
    if not (err.name or "").startswith("pipeline"):
        raise  # не хватает какой-то библиотеки — это настоящая ошибка, её надо видеть
    from mock_data import mock_recommend as recommend
    DATA_SOURCE = "mock"
    IMPORT_NOTE = "pipeline/recommend.py ещё не создан"
except ImportError as err:
    from mock_data import mock_recommend as recommend
    DATA_SOURCE = "mock"
    IMPORT_NOTE = f"в pipeline/recommend.py пока нет функции recommend ({err})"

st.set_page_config(page_title="TAŃDA — подбор подрядчиков", page_icon="✦", layout="wide",
                   initial_sidebar_state="collapsed")

st.html(f"<style>{(UI_DIR / 'style.css').read_text(encoding='utf-8')}</style>")

# ---------------------------------------------------------------- справочники интерфейса
DATE_MIN, DATE_MAX = date(2026, 9, 23), date(2026, 12, 31)
MONTHS = ["января", "февраля", "марта", "апреля", "мая", "июня", "июля",
          "августа", "сентября", "октября", "ноября", "декабря"]
SEASON_NOTES = {9: "В сентябре заняты 30–50% подрядчиков", 10: "В октябре заняты 30–50% подрядчиков",
                11: "В ноябре заняты 30–50% подрядчиков", 12: "В декабре заняты 70–80% подрядчиков"}

EVENTS = {"Свадьба": "favorite", "Той": "groups", "Корпоратив": "work",
          "Конференция": "mic", "Юбилей": "star", "День рождения": "cake"}
POPULAR_CATEGORIES = ["Ведущий", "Фотограф", "Банкетный зал", "Флорист", "Декоратор", "Подарки и сувениры"]
CATEGORY_ICONS = {"Ведущий": "mic", "Фотограф": "photo_camera", "Банкетный зал": "apartment",
                  "Флорист": "local_florist", "Декоратор": "auto_awesome", "Подарки и сувениры": "redeem",
                  "Ведущий церемонии": "record_voice_over", "Фото и видеобудки": "photo_camera_front",
                  "Отель": "hotel", "Инструменталист": "music_note"}
DEFAULT_CATEGORIES = POPULAR_CATEGORIES + ["Ведущий церемонии", "Фото и видеобудки", "Отель", "Инструменталист"]
DEFAULT_CITIES = ["Алматы", "Астана", "Зарубежье"]
BUDGET_PRESETS = {"150 000": 150000, "250 000": 250000, "400 000": 400000, "600 000": 600000}
HOURS = {"3 ч": 3, "5 ч": 5, "8 ч": 8, "Не важно": None}
LANGUAGES = {"Казахский": "казахский", "Русский": "русский", "Английский": "английский", "Не важно": None}
ANY = "Не важно"

FORM_KEYS = ["event", "category", "city", "date", "budget", "budget_preset", "hours", "lang"]
FORM_DEFAULTS = {"hours": ANY, "lang": ANY}

# ---------------------------------------------------------------- иконки (Lucide, контурные)
ICONS = {
    "arrow": '<path d="M5 12h14M13 6l6 6-6 6"/>',
    "check": '<path d="M5 12.5l4.5 4.5L19 7.5"/>',
    "info": '<circle cx="12" cy="12" r="9"/><path d="M12 7.5v5.5M12 16.5v.5"/>',
    "cal": '<rect x="3.5" y="5" width="17" height="15.5" rx="2"/><path d="M3.5 10h17M8 3v4M16 3v4"/>',
    "funnel": '<path d="M3.5 4.5h17l-6.5 8v6l-4 2v-8z"/>',
    "doc": '<rect x="5" y="3" width="14" height="18" rx="2"/><path d="M8.5 8h7M8.5 12h7M8.5 16h4"/>',
    "shield": '<path d="M12 3l7.5 3v5.5c0 4.5-3.2 8-7.5 9.5-4.3-1.5-7.5-5-7.5-9.5V6z"/><path d="M9 12l2.2 2.2L15.5 10"/>',
    "pin": '<path d="M12 21s-6.5-5.6-6.5-11a6.5 6.5 0 0 1 13 0c0 5.4-6.5 11-6.5 11z"/><circle cx="12" cy="10" r="2.3"/>',
    "users": '<circle cx="9" cy="8" r="3.5"/><path d="M2.5 20c.8-3.6 3.4-5.5 6.5-5.5s5.7 1.9 6.5 5.5"/><circle cx="17" cy="9" r="2.5"/><path d="M16.5 14.6c2.6.2 4.4 2 5 5.4"/>',
    "wallet": '<rect x="3" y="6.5" width="18" height="13" rx="2"/><path d="M16 13h2M3 10.5h18"/>',
    "chat": '<path d="M4 5.5h16v10H9l-4.5 3.5v-3.5H4z"/>',
    "clock": '<circle cx="12" cy="12" r="8.5"/><path d="M12 7.5V12l3 2"/>',
}
ACCENT, ON_ACCENT, TEXT_MUTED, INK_ICON, DANGER = "#D8BD92", "#1A1611", "#ABA396", "#8A6A3B", "#E9A28B"


def svg(name, size=24, color=ACCENT, width=1.6):
    return (f'<svg width="{size}" height="{size}" viewBox="0 0 24 24" fill="none" stroke="{color}" '
            f'stroke-width="{width}" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">'
            f'{ICONS[name]}</svg>')


def esc(value) -> str:
    return html.escape(str(value)) if value is not None else ""


def money(value) -> str:
    if isinstance(value, (int, float)):
        return f"{int(value):,}".replace(",", "\u00a0") + "\u00a0₸"
    return esc(value)


def date_words(d: date, with_year=True) -> str:
    return f"{d.day} {MONTHS[d.month - 1]}" + (f" {d.year}" if with_year else "")


def as_list(value) -> list:
    if value is None or value == "":
        return []
    if isinstance(value, (list, tuple)):
        return [v for v in value if v not in (None, "")]
    return [value]


def show(html_text: str):
    st.html(html_text)


# ---------------------------------------------------------------- варианты для формы из датасета
@st.cache_data
def load_options():
    """Список категорий и городов берём из CSV в data/, если он есть. Это только подписи для формы."""
    categories, cities = set(), set()
    for path in sorted((ROOT / "data").glob("*.csv")):
        try:
            with open(path, encoding="utf-8-sig", newline="") as f:
                for row in csv.DictReader(f):
                    for c in (row.get("categories") or "").split("|"):
                        if c.strip():
                            categories.add(c.strip())
                    if (row.get("city") or "").strip():
                        cities.add(row["city"].strip())
        except Exception:
            continue
    ordered_cats = [c for c in POPULAR_CATEGORIES if c in categories] + sorted(categories - set(POPULAR_CATEGORIES))
    ordered_cities = [c for c in DEFAULT_CITIES if c in cities] + sorted(cities - set(DEFAULT_CITIES))
    return (ordered_cats or DEFAULT_CATEGORIES), (ordered_cities or DEFAULT_CITIES)


CATEGORIES, CITIES = load_options()

# ---------------------------------------------------------------- состояние
SCREENS = ("home", "quiz", "results")
qp_screen = st.query_params.get("screen")
if qp_screen:
    st.session_state.screen = qp_screen if qp_screen in SCREENS else "home"
    st.query_params.clear()
st.session_state.setdefault("screen", "home")
st.session_state.setdefault("form", dict(FORM_DEFAULTS))
st.session_state.setdefault("show_all_cats", False)
st.session_state.setdefault("tried", False)
if st.session_state.screen == "results" and "result" not in st.session_state:
    st.session_state.screen = "quiz"


def go(screen):
    st.session_state.screen = screen


def toggle_categories():
    st.session_state.show_all_cats = not st.session_state.show_all_cats


def apply_budget_preset():
    label = st.session_state.get("budget_preset")
    if label:
        st.session_state.budget = BUDGET_PRESETS[label]


def budget_typed():
    label = st.session_state.get("budget_preset")
    if label and BUDGET_PRESETS.get(label) != st.session_state.get("budget"):
        st.session_state.budget_preset = None


def hours_value(label):
    if not label or label == ANY:
        return None
    if label in HOURS:
        return HOURS[label]
    return float(str(label).removesuffix(" ч").replace(",", "."))


def apply_text_query():
    """Fill a fresh form before widgets render; the user reviews it before search."""
    try:
        with st.spinner("ИИ разбирает запрос…"):
            parsed = asyncio.run(parse_user_query(st.session_state.get("request_text", "")))
        event_date = date.fromisoformat(parsed.date) if parsed.date else None
        if event_date and not DATE_MIN <= event_date <= DATE_MAX:
            raise ValueError("Выберите дату с 23 сентября по 31 декабря 2026 года.")
        if parsed.budget is not None and parsed.budget > 100_000_000:
            raise ValueError("Максимальный бюджет в форме — 100 000 000 ₸.")
        form = {
            "event": next((name for name in EVENTS if name.casefold() == parsed.event_type), None),
            "category": parsed.category,
            "city": parsed.city,
            "date": event_date,
            "budget": parsed.budget,
            "budget_preset": None,
            "hours": f"{parsed.hours:g} ч" if parsed.hours is not None else ANY,
            "lang": next((name for name, value in LANGUAGES.items() if value == parsed.language),
                         parsed.language.capitalize() if parsed.language else ANY),
        }
        if not any(value is not None for value in parsed.model_dump().values()):
            raise ValueError("Не удалось распознать параметры. Уточните запрос или заполните форму ниже.")
    except (ValueError, TypeError) as error:
        st.session_state.parse_error = "Не удалось распознать корректные параметры. Уточните запрос или заполните форму."
        st.session_state.parse_notice = ""
        return
    except Exception as error:
        st.session_state.parse_error = error_message(error)
        st.session_state.parse_notice = ""
        return

    st.session_state.form = form
    for key, value in form.items():
        st.session_state[key] = value
    st.session_state.show_all_cats = parsed.category not in POPULAR_CATEGORIES
    st.session_state.tried = False
    st.session_state.search_error = ""
    st.session_state.parse_error = ""
    st.session_state.parse_notice = (
        "LLM разобрала запрос и перенесла параметры в форму. Проверьте их и заполните пропуски, "
        "затем нажмите «Показать 3 лучших варианта». Дата без года относится к 2026 году."
    )


def missing_fields(form) -> dict:
    errors = {}
    if not form.get("event"):
        errors["event"] = "Выберите мероприятие"
    if not form.get("category"):
        errors["category"] = "Выберите, кто нужен"
    if not form.get("city"):
        errors["city"] = "Выберите город"
    if not form.get("date"):
        errors["date"] = "Выберите дату"
    elif not (DATE_MIN <= form["date"] <= DATE_MAX):
        errors["date"] = "Календари подрядчиков доступны с 23 сентября по 31 декабря 2026"
    if form.get("budget") is None:
        errors["budget"] = "Укажите бюджет"
    return errors


def build_query(form) -> dict:
    return {
        "city": form["city"],
        "date": form["date"].isoformat(),
        "event_type": form["event"].lower(),
        "category": form["category"],
        "budget": int(form["budget"]),
        "hours": hours_value(form.get("hours")),
        "language": LANGUAGES.get(form.get("lang"), str(form.get("lang") or "").casefold() or None),
    }


def run_search(form):
    """Вызывает воронку и сохраняет результат. Возвращает True, если всё прошло."""
    query = build_query(form)
    prev_query, prev_result = st.session_state.get("query"), st.session_state.get("result")
    started = time.perf_counter()
    try:
        with st.spinner("Подбираем…"):
            result = recommend(query)
        if result.get("cards"):
            with st.spinner("ИИ пишет объяснения по фактам…"):
                result = asyncio.run(polish_result(result, query))
    except Exception as err:  # показываем словами, а не красным экраном
        st.session_state.search_error = f"Не удалось получить подбор. Попробуйте ещё раз. ({type(err).__name__}: {err})"
        return False
    st.session_state.search_error = ""
    st.session_state.elapsed = time.perf_counter() - started
    st.session_state.prev_query, st.session_state.prev_result = prev_query, prev_result
    st.session_state.query, st.session_state.result = query, result
    st.session_state.screen = "results"
    return True


# ---------------------------------------------------------------- общие куски разметки
def nav_html(solid=False) -> str:
    return (
        f'<div class="t"><header class="t-nav{" solid" if solid else ""}">'
        '<a class="t-logo" href="?screen=home" target="_self"><b>TAŃDA</b><span>подбор подрядчиков</span></a>'
        '<nav aria-label="Основное меню">'
        '<a href="?screen=home" target="_self">Как это работает</a>'
        '<a href="?screen=quiz" target="_self">Категории</a>'
        '<a href="?screen=home" target="_self">О данных</a></nav>'
        f'<a class="t-navbtn" href="?screen=quiz" target="_self">Подобрать {svg("arrow", 18, "#F4EFE7", 2)}</a>'
        '</header></div>'
    )


def page_background(color: str):
    show(f"<style>.stApp {{ background: {color}; }}</style>")


# ================================================================= ЭКРАН 1: ГЛАВНАЯ
def render_home():
    page_background("#F3EFE8")
    with st.container(key="hero"):
        show(nav_html() + (
            '<div class="t"><div class="t-hero">'
            '<span class="t-eyebrow">Ведущий · фотограф · зал · флорист · декор</span>'
            '<h1>Ваш праздник — в надёжных руках. <span>Найдём их за минуту.</span></h1>'
            '<p>Покажем трёх лучших подрядчиков, которые свободны в ваш день и укладываются в бюджет — '
            'и объясним, почему именно они.</p></div></div>'))
        _, mid, _ = st.columns([1, 1, 1])
        with mid:
            st.button("Подобрать подрядчика", type="primary", key="cta_hero", on_click=go, args=("quiz",),
                      icon=":material/arrow_forward:", icon_position="right", width="stretch")
        checks = [("pin", "Город", "Работает в вашем городе"), ("users", "Формат", "Проводит ваш тип мероприятия"),
                  ("cal", "Дата", "Свободен в ваш день"), ("wallet", "Бюджет", "Цена укладывается в сумму"),
                  ("chat", "Язык", "Ведёт на нужном языке"), ("clock", "Часы", "Готов работать нужное время")]
        cells = "".join(
            f'<div class="t-cond"><div class="top">{svg(i, 28, ACCENT, 1.5)}<span class="num">0{n + 1}</span></div>'
            f'<b>{t}</b><span class="d">{d}</span></div>' for n, (i, t, d) in enumerate(checks))
        cells += (f'<div class="t-cond final">{svg("check", 28, ON_ACCENT, 2)}<b>До 3 вариантов</b>'
                  '<span class="d">И объяснение, чем каждый лучше других</span></div>')
        show('<div class="t"><section class="t-checks"><div><h2>Что мы проверяем за вас</h2>'
             '<div class="sub">Каждого подрядчика из каталога — по шести условиям. '
             'Остаются только те, кто подходит по всем</div></div>'
             f'<div class="t-grid7">{cells}</div></section></div>')

    steps = [("funnel", "Отбираем свободных", "Проверяем город, формат, бюджет, язык и занятость на вашу дату. "
              "Занятые в выдачу не попадают.", False),
             ("doc", "Объясняем выбор", "По каждому варианту — 1–2 предложения: чем он подходит и чем отличается "
              "от двух других. Без общих фраз.", True),
             ("shield", "Говорим честно", "Если подходит меньше трёх или никто — показываем, где отсеялись "
              "кандидаты и что можно изменить.", False)]
    step_html = "".join(
        f'<div class="t-step{" dark" if dark else ""}"><div class="head"><span class="circle">'
        f'{svg(i, 26, ACCENT if dark else INK_ICON)}</span>{"<span class=t-badge>Главное</span>" if dark else ""}</div>'
        f'<b>{t}</b><p>{d}</p></div>' for i, t, d, dark in steps)
    trust = [("cal", "Проверяем занятость", "Календари подрядчиков на 100 дней вперёд"),
             ("funnel", "Не больше трёх", "Короткий список вместо бесконечной ленты"),
             ("shield", "Только рекомендация", "Без заявок и звонков — решаете вы")]
    trust_html = "".join(f'<div>{svg(i, 40, ACCENT, 1.3)}<div><b>{t}</b><span>{d}</span></div></div>'
                         for i, t, d in trust)
    show('<div class="t">'
         '<section class="t-how" id="how"><h2>Как это работает</h2>'
         '<div class="sub">Мы не удлиняем список — помогаем выбрать из каталога вашего города</div>'
         f'<div class="t-grid3">{step_html}</div></section>'
         f'<section class="t-trust" id="trust">{trust_html}</section>'
         '<section class="t-final"><h2>Подбор займёт около минуты</h2>'
         '<p>Шесть вопросов — и три варианта с объяснением</p></section></div>')
    with st.container(key="final_row"):
        _, mid, _ = st.columns([1.3, 1, 1.3])
        with mid:
            st.button("Начать подбор", type="primary", key="cta_final", on_click=go, args=("quiz",),
                      icon=":material/arrow_forward:", icon_position="right", width="stretch")


# ================================================================= ЭКРАН 2: ПОДБОР
def render_quiz():
    page_background("#FFFFFF")
    form = st.session_state.form
    # восстанавливаем выбор, если вернулись с экрана результата
    for key in FORM_KEYS:
        if key not in st.session_state and form.get(key) is not None:
            st.session_state[key] = form[key]

    tried = st.session_state.tried
    current = {k: st.session_state.get(k, form.get(k)) for k in FORM_KEYS}
    errors = missing_fields(current) if tried else {}

    def picked(value):
        if value:
            show(f'<div class="t"><div class="t-picked">Выбрано: <b>{esc(value)}</b></div></div>')

    def err(key):
        if key in errors:
            show(f'<div class="t"><div class="t-err">{errors[key]}</div></div>')

    show(nav_html(solid=True))
    with st.container(key="quiz_panel"):
        step1 = bool(current.get("event") and current.get("category"))
        step2 = bool(current.get("city") and current.get("date"))
        step3 = current.get("budget") is not None
        cur = 0 if not step1 else 1 if not step2 else 2
        progress = "".join(
            f'<div class="{"done " if done else ""}{"cur" if n == cur else ""}"><i></i>Шаг {n + 1} · {label}</div>'
            for n, (label, done) in enumerate([("Что нужно", step1), ("Когда и где", step2), ("Детали", step3)]))
        show('<div class="t"><div class="t-qhead"><h1>Уточним детали</h1>'
             '<p>Чем точнее параметры, тем конкретнее объяснения</p></div></div>'
             f'<div class="t"><div class="t-progress">{progress}</div></div>')

        show('<div class="t"><div class="t-sect">Опишите мероприятие своими словами</div>'
             '<p>Укажите город, дату, мероприятие, подрядчика и бюджет. '
             'Язык и длительность — по желанию.</p></div>')
        st.text_area(
            "Запрос обычным текстом", key="request_text", height=110,
            placeholder="Нужен ведущий на свадьбу в Алматы 7 октября, бюджет 1,2 млн, "
                        "на 5 часов, на русском",
            label_visibility="collapsed",
        )
        st.button("Разобрать запрос с ИИ", key="parse_request", on_click=apply_text_query)
        st.caption("ИИ извлекает параметры. Перед поиском проверьте заполненную форму.")
        if st.session_state.get("parse_error"):
            show(f'<div class="t"><div class="t-err">{esc(st.session_state.parse_error)}</div></div>')
        if st.session_state.get("parse_notice"):
            show(f'<div class="t"><div class="t-picked">{esc(st.session_state.parse_notice)}</div></div>')

        show('<div class="t"><div class="t-sect" id="sect-event">Какое мероприятие</div></div>')
        st.pills("Какое мероприятие", list(EVENTS), key="event", required=True,
                 format_func=lambda x: f":material/{EVENTS[x]}: {x}", label_visibility="collapsed", width="stretch")
        picked(st.session_state.get("event"))
        err("event")

        show('<div class="t"><div class="t-sect" id="sect-category">Кто нужен</div></div>')
        cat_options = CATEGORIES if st.session_state.show_all_cats else \
            [c for c in CATEGORIES if c in POPULAR_CATEGORIES][:6] or CATEGORIES[:6]
        chosen = st.session_state.get("category")
        if chosen and chosen not in cat_options:
            cat_options = cat_options + [chosen]
        st.pills("Кто нужен", cat_options, key="category", required=True,
                 format_func=lambda x: f":material/{CATEGORY_ICONS.get(x, 'category')}: {x}",
                 label_visibility="collapsed", width="stretch")
        picked(st.session_state.get("category"))
        err("category")
        rest = len(CATEGORIES) - 6
        if rest > 0:
            st.button("Свернуть" if st.session_state.show_all_cats else f"Ещё {rest} категорий",
                      type="tertiary", key="more_cats", on_click=toggle_categories)

        c1, c2, c3 = st.columns(3)
        with c1, st.container(key="f_city"):
            value = current.get("city")
            show(f'<div class="t"><div class="t-fieldlabel">Город</div>'
                 f'<div class="t-fieldvalue{"" if value else " empty"}">{esc(value or "Не выбран")}</div></div>')
            city_options = list(CITIES)
            if value and value not in city_options:
                city_options.append(value)
            st.pills("Город", city_options, key="city", required=True, label_visibility="collapsed")
            err("city")
        with c2, st.container(key="f_date"):
            value = current.get("date")
            show(f'<div class="t"><div class="t-fieldlabel">Дата</div>'
                 f'<div class="t-fieldvalue{"" if value else " empty"}">'
                 f'{date_words(value) if value else "Не выбрана"}</div></div>')
            first_time = {} if "date" in st.session_state else {"value": None}
            st.date_input("Дата", min_value=DATE_MIN, max_value=DATE_MAX, key="date",
                          format="DD.MM.YYYY", label_visibility="collapsed", **first_time)
            if value:
                show(f'<div class="t"><div class="t-note">{SEASON_NOTES.get(value.month, "")}</div></div>')
            err("date")
        with c3, st.container(key="f_budget"):
            value = current.get("budget")
            show(f'<div class="t"><div class="t-fieldlabel">Бюджет</div>'
                 f'<div class="t-fieldvalue{"" if value else " empty"}">'
                 f'{"до " + money(value) if value else "Не указан"}</div></div>')
            first_time = {} if "budget" in st.session_state else {"value": None}
            st.number_input("Бюджет, ₸", min_value=0, max_value=100_000_000, step=10_000, key="budget",
                            placeholder="Например, 400000", on_change=budget_typed, label_visibility="collapsed",
                            **first_time)
            st.pills("Быстрый выбор бюджета", list(BUDGET_PRESETS), key="budget_preset",
                     on_change=apply_budget_preset, label_visibility="collapsed")
            err("budget")

        c4, c5 = st.columns(2)
        with c4, st.container(key="f_hours"):
            value = current.get("hours") or ANY
            show(f'<div class="t"><div class="t-fieldlabel">Длительность, необязательно</div>'
                 f'<div class="t-fieldvalue">{esc(value)}</div></div>')
            hour_options = list(HOURS)
            if value not in hour_options:
                hour_options.insert(-1, value)
            st.pills("Длительность", hour_options, key="hours", required=True, label_visibility="collapsed")
        with c5, st.container(key="f_lang"):
            value = current.get("lang") or ANY
            show(f'<div class="t"><div class="t-fieldlabel">Язык, необязательно</div>'
                 f'<div class="t-fieldvalue">{esc(value)}</div></div>')
            language_options = list(LANGUAGES)
            if value not in language_options:
                language_options.insert(-1, value)
            st.pills("Язык", language_options, key="lang", required=True, label_visibility="collapsed")

        submitted = st.button("Показать 3 лучших варианта", type="primary", key="submit",
                              icon=":material/arrow_forward:", icon_position="right", width="stretch")
        if st.session_state.get("search_error"):
            show(f'<div class="t"><div class="t-err" style="text-align:center">'
                 f'{esc(st.session_state.search_error)}</div></div>')
        show('<div class="t"><div class="t-footnote">Никаких заявок и звонков — только рекомендация</div></div>')

    # сохраняем форму отдельно от виджетов: Streamlit стирает их состояние, когда экран скрыт
    st.session_state.form = {k: st.session_state.get(k) for k in FORM_KEYS}

    if submitted:
        form = st.session_state.form
        if missing_fields(form):
            st.session_state.tried = True
            st.rerun()
        elif run_search(form):
            st.session_state.tried = False
            st.rerun()
        else:
            st.rerun()


# ================================================================= ЭКРАН 3: РЕЗУЛЬТАТ
def date_change_banner(query, result) -> str:
    """Баннер «изменилось из-за даты»: только если между запросами поменялась одна дата."""
    prev_q, prev_r = st.session_state.get("prev_query"), st.session_state.get("prev_result")
    if not prev_q or not prev_r or prev_q.get("date") == query.get("date"):
        return ""
    if any(prev_q.get(k) != query.get(k) for k in query if k != "date"):
        return ""
    before = {c.get("id"): c.get("name") for c in prev_r.get("cards") or []}
    after = {c.get("id"): c.get("name") for c in result.get("cards") or []}
    if before.keys() == after.keys():
        return ""
    reasons = {r.get("id"): "; ".join(x.get("text", "") for x in r.get("reasons") or [])
               for r in result.get("rejected") or []}
    parts = []
    for cid in before.keys() - after.keys():
        why = reasons.get(cid)
        parts.append(f"{esc(before[cid])} выпал(а) из выдачи" + (f": {esc(why)}" if why else ""))
    for cid in after.keys() - before.keys():
        parts.append(f"{esc(after[cid])} теперь проходит")
    prev_day = date.fromisoformat(prev_q["date"])
    return (f'<div class="t-banner">{svg("cal", 24)}<div><b>Выдача изменилась из-за занятости</b>'
            f'<span>По сравнению с {date_words(prev_day, False)}: {". ".join(parts)}.</span></div></div>')


def card_html(card: dict, rank: int, best: bool) -> str:
    cats = ", ".join(esc(c) for c in as_list(card.get("categories")))
    meta = " · ".join(x for x in [cats, esc(card.get("city"))] if x)
    price = card.get("price")
    price_text = ("от " + money(price)) if isinstance(price, (int, float)) else esc(price or "Цена не указана")
    icon_color = ACCENT if best else INK_ICON
    available_color = "#9FDCB3" if best else "#216E39"
    lis = "".join(
        f'<li style="color:{available_color}">{svg("check", 18, available_color, 2.2)}{esc(x)}</li>'
        for x in as_list(card.get("availability"))
    )
    lis += "".join(f'<li>{svg("info", 18, icon_color)}{esc(x)}</li>' for x in as_list(card.get("notes")))
    flags = ""
    source = card.get("explanation_source")
    if source in ("llm", "llm_cache"):
        flags += '<span class="t-badge">Объяснение от ИИ' + (" · из кэша" if source == "llm_cache" else "") + '</span>'
    elif source == "template":
        flags += '<span class="t-badge warn">Объяснение по шаблону</span>'
    if card.get("synthetic"):
        flags += '<span class="t-badge syn">Синтетический профиль</span>'
    elif "synthetic" in card:
        flags += '<span class="t-badge">Реальный профиль</span>'
    if card.get("price_imputed"):
        flags += '<span class="t-badge warn">Цена оценочная — уточните</span>'
    if card.get("city_imputed"):
        flags += '<span class="t-badge warn">Город проставлен при подготовке — уточните</span>'
    facts = ""
    if card.get("template_explanation"):
        facts += f'<div><b>Исходные факты</b><br>{esc(card["template_explanation"])}</div>'
    for f in as_list(card.get("facts")):
        if isinstance(f, dict):
            facts += f'<div><b>{esc(f.get("fact"))}</b><br>«{esc(f.get("quote"))}»</div>'
    parts = card.get("score_parts") or {}
    if isinstance(parts, dict) and parts:
        rows = "<br>".join(f"{esc(k)}: {v:.2f}" if isinstance(v, (int, float)) else f"{esc(k)}: {esc(v)}"
                           for k, v in parts.items())
        facts += f"<div><b>Из чего сложился балл</b><br>{rows}</div>"
    if card.get("score") is not None:
        facts += f'<div><b>Итого: {esc(card["score"])}</b></div>'
    if card.get("rank_reason"):
        facts += f'<div><b>Почему это место</b><br>{esc(card["rank_reason"])}</div>'
    details = (f'<details><summary>На чём основано объяснение</summary><div class="facts">{facts}</div></details>'
               if facts else "")
    badge = '<span class="t-badge">Лучшее совпадение</span>' if best else ""
    distinctive = f'<p class="expl"><strong>{esc(card["distinctive"])}</strong></p>' if card.get("distinctive") else ""
    ai_notice = f'<p class="expl">{esc(card["ai_notice"])}</p>' if card.get("ai_notice") else ""
    return (f'<article class="t-card{" best" if best else ""}">'
            f'<div class="row"><span class="lab">Вариант {rank}</span>{badge}</div>'
            f'<div class="name">{esc(card.get("name"))}</div><div class="meta">{meta}</div>'
            f'<div class="price">{price_text}</div>{distinctive}<p class="expl">{esc(card.get("explanation"))}</p>'
            f'<ul>{lis}</ul><div class="flags">{flags}</div>{ai_notice}<div class="grow"></div>{details}</article>')


def funnel_numbers(funnel) -> str:
    out = []
    for n, step in enumerate(funnel):
        if n:
            out.append(f'<div style="padding-top:8px">{svg("arrow", 18, TEXT_MUTED)}</div>')
        label = step.get("step") or step.get("label") or f"Шаг {n + 1}"
        out.append(f'<div><b>{esc(step.get("count"))}</b><span>{esc(label)}</span></div>')
    return f'<div class="funnel">{"".join(out)}</div>'


def funnel_bars(funnel) -> str:
    top = max([s.get("count") or 0 for s in funnel] + [1])
    rows = ""
    for index, s in enumerate(funnel, start=1):
        n = s.get("count") or 0
        bar = f'<div class="bar" style="width:{max(4, round(n / top * 100))}%"></div>' if n else '<div class="bar zero"></div>'
        label = s.get("step") or s.get("label") or f"Шаг {index}"
        rows += f'<div><span>{esc(label)}</span>{bar}<b>{n}</b></div>'
    return f'<div class="t-bars">{rows}</div>'


def render_rejected(result):
    rejected = result.get("rejected") or []
    if not rejected:
        return
    items = []
    for profile in rejected:
        reasons = []
        for reason in profile.get("reasons") or []:
            text = (reason.get("text") or reason.get("code")) if isinstance(reason, dict) else reason
            if text:
                reasons.append(f"<li>{esc(text)}</li>")
        name = profile.get("name") or profile.get("id") or "Подрядчик"
        items.append(f'<li style="margin:16px 0"><b>{esc(name)}</b><ul>{"".join(reasons)}</ul></li>')
    opened = " open" if result.get("outcome") == "none_passed" else ""
    show('<div class="t"><section class="t-results"><div class="t-box">'
         f'<details{opened}><summary style="cursor:pointer;font-size:20px;font-weight:600">'
         f'Почему не попали остальные ({len(rejected)})</summary>'
         f'<ol>{"".join(items)}</ol></details></div></section></div>')


def apply_suggestion(patch: dict):
    form = dict(st.session_state.form)
    if "date" in patch:
        form["date"] = date.fromisoformat(patch["date"])
    if "budget" in patch or "budget_kzt" in patch:
        form["budget"] = int(patch.get("budget", patch.get("budget_kzt")))
        form["budget_preset"] = None
    if "city" in patch:
        form["city"] = patch["city"]
    st.session_state.form = form
    for key in FORM_KEYS:
        st.session_state.pop(key, None)
    run_search(form)


def render_results():
    page_background("#F3EFE8")
    query, result = st.session_state.query, st.session_state.result
    outcome = result.get("outcome")
    cards = result.get("cards") or []
    matched = outcome == "matched" and cards

    chips_src = [esc(st.session_state.form.get("event")), esc(query.get("category")), esc(query.get("city")),
                 date_words(date.fromisoformat(query["date"])), "до " + money(query.get("budget"))]
    if query.get("hours"):
        chips_src.append(f'{query["hours"]} ч')
    if query.get("language"):
        chips_src.append(esc(query["language"].capitalize()))
    chips = "".join(f"<span>{c}</span>" for c in chips_src if c)
    if matched and len(cards) >= 3:
        icon = svg("check", 34, ACCENT, 2)
    elif matched:
        icon = svg("info", 34, ACCENT, 2)
    else:
        icon = svg("info", 34, DANGER, 2)
    mock = (f'<span class="t-mock" title="{esc(IMPORT_NOTE)}">Демо-данные: воронка ещё не подключена</span>'
            if DATA_SOURCE == "mock" else "")

    with st.container(key="res_top"):
        show(nav_html() + '<div class="t"><div class="t-restop">'
             f'<div class="t-qchips">{chips}</div>{mock}'
             f'<div class="t-status">{icon}<h1 aria-live="polite">{esc(result.get("headline"))}</h1></div>'
             f'<p class="t-summary">{esc(result.get("summary"))}</p></div></div>')
        st.button("Изменить параметры", type="tertiary", key="edit", on_click=go, args=("quiz",))

    banner = date_change_banner(query, result)
    elapsed = st.session_state.get("elapsed", 0)
    meta = result.get("meta") or {}
    time_text = f"Ответ за {elapsed:.1f} с".replace(".", ",")
    if meta.get("cached"):
        time_text += " · из кэша"

    if matched:
        grid = "".join(card_html(c, i + 1, i == 0) for i, c in enumerate(cards[:3]))
        near = [r for r in result.get("rejected") or [] if len(r.get("reasons") or []) == 1][:3]
        near_html = ""
        if near:
            items = '<i></i>'.join(f'<span><b>{esc(r.get("name"))}</b> — {esc(r["reasons"][0].get("text"))}</span>'
                                   for r in near)
            near_html = f'<div class="t-near"><span class="lab">Чуть не вошли</span>{items}</div>'
        verified = (f'<span style="display:flex;gap:8px;align-items:center">{svg("check", 16, ACCENT, 2)}'
                    'Факты в объяснениях сверены с профилями</span>') if meta.get("explanations_verified") else ""
        funnel = funnel_numbers(result["funnel"]) if result.get("funnel") else ""
        fallback = ('<div class="scores">Объяснения показаны в упрощённом виде</div>'
                    if meta.get("fallback_used") else "")
        title = "Как мы отобрали эти три варианта" if len(cards) >= 3 else "Как мы искали"
        how = (f'<div class="t-howbar"><div class="row"><div class="title">{title}</div>'
               f'<div class="meta">{verified}<span>{time_text}</span></div></div>{funnel}{fallback}</div>')
        show(f'<div class="t">{banner}<section class="t-results">'
             f'<div class="t-grid3">{grid}</div>{near_html}{how}</section></div>')
        render_rejected(result)
        return

    # ---- исходы no_category и none_passed
    day = date.fromisoformat(query["date"])
    season = result.get("season_note")
    if not season and day.month == 12 and outcome == "none_passed":
        season = {"title": "Конец декабря — пик сезона",
                  "text": "В декабре заняты 70–80% подрядчиков, на выходные почти никого не остаётся. "
                          "Это не ошибка поиска. Если дата гибкая, ноябрь даст больше выбора."}
    if outcome == "none_passed":
        body = funnel_bars(result["funnel"]) if result.get("funnel") else ""
        box = f'<div class="t-box"><h2>Где отсеялись кандидаты</h2><p>{esc(result.get("summary"))}</p>{body}</div>'
    else:
        box = f'<div class="t-box"><h2>Почему так</h2><p>{esc(result.get("summary"))}</p></div>'
    season_html = (f'<div class="t-season">{svg("cal", 34, "#6E4A07", 1.5)}<h2>{esc(season.get("title"))}</h2>'
                   f'<p>{esc(season.get("text"))}</p></div>') if season else ""
    show(f'<div class="t"><section class="t-results">'
         f'<div class="t-emptygrid{"" if season_html else " one"}">{box}{season_html}</div>'
         f'<div class="t-h2">{"Что изменить, чтобы нашёлся вариант" if outcome == "none_passed" else "Что можно сделать"}</div>'
         f'</section></div>')

    suggestions = result.get("suggestions") or []
    with st.container(key="sug_row"):
        if suggestions:
            cols = st.columns(min(len(suggestions), 2))
            for i, sug in enumerate(suggestions[:2]):
                with cols[i]:
                    show(f'<div class="t"><div class="t-sug{" dark" if i == 0 else ""}">'
                         f'<span class="lab">{esc(sug.get("label"))}</span><span class="val">{esc(sug.get("value"))}</span>'
                         f'<p>{esc(sug.get("text"))}</p></div></div>')
                    if st.button(sug.get("button") or "Применить", type="primary" if i == 0 else "secondary",
                                 key=f"sug_{i}", width="stretch"):
                        apply_suggestion(sug.get("patch") or {})
                        st.rerun()
        else:
            _, mid, _ = st.columns([1.3, 1, 1.3])
            with mid:
                st.button("Изменить параметры", type="primary", key="edit_bottom", on_click=go, args=("quiz",),
                          width="stretch")
    render_rejected(result)


# ================================================================= роутер
{"home": render_home, "quiz": render_quiz, "results": render_results}[st.session_state.screen]()
