from app.handlers.recipes import parse_one_message_recipe
from app.services.ingredients import format_ingredient


def test_parse_one_message_recipe_with_blank_line_and_steps():
    draft, error = parse_one_message_recipe(
        "Борщ\n"
        "говядина 500 г\n"
        "картошка 4 шт\n"
        "\n"
        "Нарезать овощи.\n"
        "Варить до готовности."
    )

    assert error is None
    assert draft.name == "Борщ"
    assert [format_ingredient(item.name, item.amount, item.unit) for item in draft.ingredients] == [
        "говядина — 500 г",
        "картошка — 4 шт",
    ]
    assert draft.steps == "Нарезать овощи.\nВарить до готовности."


def test_parse_one_message_recipe_without_blank_line_has_no_steps():
    draft, error = parse_one_message_recipe(
        "Омлет\n"
        "яйца 3 шт\n"
        "молоко 100 мл"
    )

    assert error is None
    assert draft.name == "Омлет"
    assert [item.name for item in draft.ingredients] == ["яйца", "молоко"]
    assert draft.steps == ""


def test_parse_one_message_recipe_with_blank_line_but_without_steps():
    draft, error = parse_one_message_recipe(
        "Салат\n"
        "огурец 2 шт\n"
        "соль по вкусу\n"
        "\n"
    )

    assert error is None
    assert draft.name == "Салат"
    assert [item.name for item in draft.ingredients] == ["огурец", "соль"]
    assert draft.steps == ""


def test_parse_one_message_recipe_requires_ingredient():
    draft, error = parse_one_message_recipe("Пустой рецепт")

    assert draft is None
    assert error == "Нужен хотя бы один ингредиент."
