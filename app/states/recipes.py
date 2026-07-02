from aiogram.fsm.state import State, StatesGroup


class AddRecipe(StatesGroup):
    name = State()
    category = State()
    ingredients = State()
    confirm_ingredients = State()
    steps = State()
    confirm_save = State()


class EditRecipe(StatesGroup):
    name = State()
    category = State()
    ingredients = State()
    steps = State()


class Shopping(StatesGroup):
    browsing = State()
    manual = State()
