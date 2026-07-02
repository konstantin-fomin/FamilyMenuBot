import pytest

from app.services.ingredients import parse_ingredient_line, parse_ingredients


@pytest.mark.parametrize(
    ("line", "name", "amount", "unit"),
    [
        ("курица 1.5 кг", "курица", 1500, "г"),
        ("молоко 0,5 л", "молоко", 500, "мл"),
        ("картошка 6 шт", "картошка", 6, "шт"),
        ("сахар 2 ст.л.", "сахар", 2, "ст.л."),
        ("соль по вкусу", "соль", None, "по вкусу"),
        ("перец", "перец", None, "по вкусу"),
        ("1/2 ч.л. паприка", "паприка", 0.5, "ч.л."),
        ("2 яйца", "яйца", 2, "шт"),
    ],
)
def test_parse_ingredient_line(line, name, amount, unit):
    ingredient = parse_ingredient_line(line)

    assert ingredient.name == name
    assert ingredient.amount == amount
    assert ingredient.unit == unit


def test_parse_ingredients_skips_empty_lines():
    ingredients = parse_ingredients("курица 1 кг\n\nсоль по вкусу")

    assert [(item.name, item.amount, item.unit) for item in ingredients] == [
        ("курица", 1000, "г"),
        ("соль", None, "по вкусу"),
    ]
