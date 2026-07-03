from __future__ import annotations

import re

from app.database import Database, ShoppingDepartment


DEFAULT_DEPARTMENT_NAME = "📦 Прочее"

DEPARTMENT_STEMS = {
    "🥬 Овощи и фрукты": (
        "карто",
        "лук",
        "морков",
        "яблок",
        "банан",
        "помидор",
        "томат",
        "огур",
        "капуст",
        "свек",
        "перец",
        "кабач",
        "баклаж",
        "чеснок",
        "зелень",
        "укроп",
        "петруш",
        "салат",
        "лимон",
        "апельсин",
        "груш",
        "виноград",
        "авокад",
        "тыкв",
        "редис",
        "имбир",
        "ягод",
    ),
    "🥩 Мясо и рыба": (
        "куриц",
        "курин",
        "филе",
        "говядин",
        "свинин",
        "индей",
        "рыб",
        "фарш",
        "лосос",
        "семг",
        "треск",
        "тунец",
        "кревет",
        "морепродукт",
        "бекон",
        "ветчин",
        "колбас",
        "сосиск",
        "котлет",
        "печен",
        "ребр",
        "грудк",
    ),
    "🥛 Молочное и яйца": (
        "молок",
        "сыр",
        "творог",
        "яйц",
        "сметан",
        "кефир",
        "йогурт",
        "сливк",
        "масло слив",
        "моцарел",
        "пармезан",
        "брынз",
        "ряжен",
        "простокваш",
    ),
    "🍞 Хлеб и выпечка": (
        "хлеб",
        "батон",
        "лаваш",
        "булоч",
        "булк",
        "багет",
        "тост",
        "пит",
        "круассан",
        "лепеш",
    ),
    "🥫 Бакалея": (
        "мук",
        "сахар",
        "соль",
        "круп",
        "рис",
        "греч",
        "макарон",
        "паст",
        "масло раст",
        "оливков",
        "подсолнеч",
        "овсян",
        "хлоп",
        "фасол",
        "горох",
        "чечев",
        "нут",
        "консерв",
        "томатн паст",
        "соус",
        "майонез",
        "кетчуп",
        "уксус",
        "спец",
        "перец черн",
        "паприк",
        "кориандр",
        "лавров",
        "чай",
        "кофе",
        "какао",
        "мед",
        "дрожж",
        "разрыхл",
        "паниров",
        "сухар",
    ),
    "🧊 Заморозка": (
        "заморож",
        "морожен",
        "пельмен",
        "вареник",
        "наггет",
        "замороз",
        "лед",
        "смесь овощ",
    ),
    "🧴 Бытовое": (
        "бумаг",
        "салфет",
        "пакет",
        "фольг",
        "пленк",
        "губк",
        "мыло",
        "порошок",
        "средство",
        "таблетк",
        "мусорн",
        "перчат",
        "шампун",
    ),
}


async def resolve_department(db: Database, product_name: str) -> ShoppingDepartment:
    normalized = normalize_product_name(product_name)
    manual = await db.get_product_department(normalized)
    if manual is not None:
        return manual

    department_name = detect_department_name(product_name)
    departments = await db.list_shopping_departments()
    return next(
        (department for department in departments if department.name == department_name),
        departments[-1],
    )


def detect_department_name(product_name: str) -> str:
    normalized = normalize_product_name(product_name)
    for department_name, stems in DEPARTMENT_STEMS.items():
        if any(stem in normalized for stem in stems):
            return department_name
    return DEFAULT_DEPARTMENT_NAME


def normalize_product_name(name: str) -> str:
    value = name.strip().lower().replace("ё", "е")
    value = re.sub(r"[^а-яa-z0-9\s-]", "", value)
    value = " ".join(value.split())
    if value.endswith("ки"):
        value = value[:-2] + "ка"
    elif value.endswith("ки "):
        value = value[:-3] + "ка"
    return value
