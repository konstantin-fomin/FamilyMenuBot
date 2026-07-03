from aiogram.fsm.state import State, StatesGroup


class AddRecipe(StatesGroup):
    method = State()
    name = State()
    category = State()
    one_message = State()
    one_category = State()
    servings = State()
    ingredients = State()
    confirm_ingredients = State()
    steps = State()
    photo = State()
    confirm_save = State()


class EditRecipe(StatesGroup):
    name = State()
    category = State()
    ingredients = State()
    steps = State()
    photo = State()
    servings = State()


class RecipeSearch(StatesGroup):
    query = State()


class Shopping(StatesGroup):
    browsing = State()
    manual = State()
