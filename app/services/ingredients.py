from __future__ import annotations

from dataclasses import dataclass
from fractions import Fraction
import re


TASTE_UNIT = "по вкусу"
ALLOWED_UNITS = ("г", "кг", "мл", "л", "шт", "ст.л.", "ч.л.", TASTE_UNIT)
UNIT_ALIASES = {
    "г": "г",
    "гр": "г",
    "грамм": "г",
    "грамма": "г",
    "граммов": "г",
    "кг": "кг",
    "килограмм": "кг",
    "килограмма": "кг",
    "килограммов": "кг",
    "мл": "мл",
    "миллилитр": "мл",
    "миллилитра": "мл",
    "миллилитров": "мл",
    "л": "л",
    "литр": "л",
    "литра": "л",
    "литров": "л",
    "шт": "шт",
    "шт.": "шт",
    "штука": "шт",
    "штуки": "шт",
    "штук": "шт",
    "ст.л": "ст.л.",
    "ст.л.": "ст.л.",
    "ст": "ст.л.",
    "столовая": "ст.л.",
    "столовые": "ст.л.",
    "столовых": "ст.л.",
    "ч.л": "ч.л.",
    "ч.л.": "ч.л.",
    "ч": "ч.л.",
    "чайная": "ч.л.",
    "чайные": "ч.л.",
    "чайных": "ч.л.",
}


@dataclass(frozen=True)
class ParsedIngredient:
    name: str
    amount: float | None
    unit: str


def parse_ingredients(text: str) -> list[ParsedIngredient]:
    ingredients = []
    for raw_line in text.splitlines():
        ingredient = parse_ingredient_line(raw_line)
        if ingredient is not None:
            ingredients.append(ingredient)
    return ingredients


def parse_ingredient_line(line: str) -> ParsedIngredient | None:
    cleaned = _clean_spaces(line)
    if not cleaned:
        return None

    lowered = cleaned.lower()
    if TASTE_UNIT in lowered:
        name = _clean_spaces(re.sub(TASTE_UNIT, "", cleaned, flags=re.IGNORECASE))
        return ParsedIngredient(name=name or cleaned, amount=None, unit=TASTE_UNIT)

    tokens = cleaned.split()
    for index, token in enumerate(tokens):
        amount = _parse_amount(token)
        if amount is None:
            continue

        unit = _normalize_unit(tokens[index + 1]) if index + 1 < len(tokens) else "шт"
        name_tokens = tokens[:index] + tokens[index + (2 if unit else 1) :]
        unit = unit or "шт"
        name = _clean_spaces(" ".join(name_tokens))
        if not name:
            name = _clean_spaces(" ".join(tokens[index + 1 :])) or cleaned
        amount, unit = normalize_amount(amount, unit)
        return ParsedIngredient(name=name, amount=amount, unit=unit)

    return ParsedIngredient(name=cleaned, amount=None, unit=TASTE_UNIT)


def normalize_amount(amount: float | int, unit: str) -> tuple[float, str]:
    normalized_unit = _normalize_unit(unit) or unit
    normalized_amount = float(amount)

    if normalized_unit == "кг":
        return normalized_amount * 1000, "г"
    if normalized_unit == "л":
        return normalized_amount * 1000, "мл"
    return normalized_amount, normalized_unit


def format_ingredient(name: str, amount: float | None, unit: str) -> str:
    if amount is None or unit == TASTE_UNIT:
        return f"{name} — {TASTE_UNIT}"
    return f"{name} — {_format_amount(amount)} {unit}"


def _normalize_unit(token: str) -> str | None:
    return UNIT_ALIASES.get(token.strip().lower())


def _parse_amount(token: str) -> float | None:
    value = token.strip().replace(",", ".")
    if not re.fullmatch(r"\d+(?:\.\d+)?|\d+/\d+", value):
        return None
    try:
        if "/" in value:
            return float(Fraction(value))
        return float(value)
    except (ValueError, ZeroDivisionError):
        return None


def _format_amount(amount: float) -> str:
    if amount.is_integer():
        return str(int(amount))
    return f"{amount:g}"


def _clean_spaces(value: str) -> str:
    return " ".join(value.strip().split())
