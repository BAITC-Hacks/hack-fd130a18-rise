"""Load and normalize contractor profiles from the hackathon CSV dataset."""

from __future__ import annotations

import csv
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_DATA_PATH = PROJECT_ROOT / "data" / "hackathon dataset anonymized .csv"

REQUIRED_COLUMNS = {
    "id",
    "anon_name",
    "categories",
    "city",
    "city_imputed",
    "synthetic",
    "price_from_kzt",
    "price_imputed",
    "event_formats",
    "languages",
    "max_hours",
    "busy_dates",
    "description",
}


def _split_pipe(value: str | None) -> list[str]:
    """Turn a pipe-separated CSV field into a clean list of values."""
    if not value:
        return []
    return [item.strip() for item in value.split("|") if item.strip()]


def _parse_bool(value: str | None, *, field: str, row_number: int) -> bool:
    normalized = (value or "").strip().lower()
    if normalized in {"true", "1", "yes", "да"}:
        return True
    if normalized in {"false", "0", "no", "нет"}:
        return False
    raise ValueError(
        f"Строка {row_number}: в поле {field!r} ожидалось True или False, "
        f"получено {value!r}."
    )


def _parse_optional_int(
    value: str | None, *, field: str, row_number: int
) -> int | None:
    normalized = (value or "").strip()
    if not normalized:
        return None
    try:
        return int(normalized)
    except ValueError as error:
        raise ValueError(
            f"Строка {row_number}: в поле {field!r} ожидалось целое число "
            f"или пустое значение, получено {value!r}."
        ) from error


def load_profiles(path: str | Path | None = None) -> list[dict[str, Any]]:
    """Read profiles and normalize flags, optional numbers, and pipe lists.

    When ``path`` is omitted, the loader expects the dataset at
    ``data/hackathon dataset anonymized .csv`` in the project folder.
    Each returned dictionary keeps the dataset's column names. The fields
    ``categories``, ``event_formats``, ``languages``, and ``busy_dates`` are
    lists; boolean columns are ``bool``; prices and ``max_hours`` are integers
    (or ``None`` when their CSV value is empty).
    """
    csv_path = Path(path) if path is not None else DEFAULT_DATA_PATH
    if not csv_path.is_file():
        raise FileNotFoundError(
            f"Не найден файл датасета: {csv_path}\n"
            "Сохраните CSV в папку data проекта или передайте путь в "
            "load_profiles(path)."
        )

    profiles: list[dict[str, Any]] = []
    with csv_path.open("r", encoding="utf-8-sig", newline="") as csv_file:
        reader = csv.DictReader(csv_file)
        columns = set(reader.fieldnames or [])
        missing = sorted(REQUIRED_COLUMNS - columns)
        if missing:
            raise ValueError(
                "В CSV отсутствуют обязательные столбцы: " + ", ".join(missing)
            )

        for row_number, raw in enumerate(reader, start=2):
            profile: dict[str, Any] = {
                "id": (raw.get("id") or "").strip(),
                "anon_name": (raw.get("anon_name") or "").strip(),
                "categories": _split_pipe(raw.get("categories")),
                "city": (raw.get("city") or "").strip(),
                "city_imputed": _parse_bool(
                    raw.get("city_imputed"), field="city_imputed", row_number=row_number
                ),
                "synthetic": _parse_bool(
                    raw.get("synthetic"), field="synthetic", row_number=row_number
                ),
                "price_from_kzt": _parse_optional_int(
                    raw.get("price_from_kzt"),
                    field="price_from_kzt",
                    row_number=row_number,
                ),
                "price_imputed": _parse_bool(
                    raw.get("price_imputed"), field="price_imputed", row_number=row_number
                ),
                "event_formats": _split_pipe(raw.get("event_formats")),
                "languages": _split_pipe(raw.get("languages")),
                "max_hours": _parse_optional_int(
                    raw.get("max_hours"), field="max_hours", row_number=row_number
                ),
                "busy_dates": _split_pipe(raw.get("busy_dates")),
                "description": (raw.get("description") or "").strip(),
            }
            if not profile["id"]:
                raise ValueError(f"Строка {row_number}: у профиля не заполнен id.")
            profiles.append(profile)

    return profiles
