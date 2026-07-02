# Разработка

## Локальная среда

```bash
python3 -m venv venv
venv/bin/pip install -r requirements.txt
```

Файл `.env` должен быть в корне проекта:

```env
BOT_TOKEN=1234567890:telegram-bot-token
```

Не коммитить:

- `.env`
- `venv/`
- `data/`
- `logs/`
- `__pycache__/`
- `.pytest_cache/`

## Запуск бота

```bash
venv/bin/python bot.py
```

База создается автоматически в `data/bot.db`.
Логи пишутся в `logs/bot.log`.

## Docker

Основной production-like запуск:

```bash
docker compose up -d --build
```

Контейнер:

- сервис и container name: `family-menu-bot`;
- restart policy: `unless-stopped`;
- env: `.env` через `env_file`;
- timezone: `Europe/Berlin`;
- volumes: `./data:/app/data`, `./logs:/app/logs`.

Проверка после запуска:

```bash
docker compose ps
docker compose logs --tail=100 family-menu-bot
```

## Тесты

Основная проверка:

```bash
venv/bin/pytest
```

Проверка импортов и синтаксиса:

```bash
venv/bin/python -m py_compile bot.py app/config.py app/database/storage.py app/handlers/start.py app/handlers/family.py app/handlers/menu.py
```

Проверка загрузки `.env` и формата токена:

```bash
venv/bin/python -c "import bot; from app.config import load_config; cfg = load_config(); assert cfg.bot_token"
```

## Правила изменений

- Все пользовательские тексты бота держать на русском.
- Хендлеры должны быть тонкими: Telegram-событие, проверка доступа, вызов базы или сервиса, ответ пользователю.
- SQL-логику держать в `app/database/`.
- Клавиатуры держать в `app/keyboards/`.
- Повторяемую доменную логику без Telegram API держать в `app/services/`.
- Для новой бизнес-логики добавлять тесты в `tests/`.
- Перед коммитом запускать `venv/bin/pytest`.

## Добавление разделов

Рекомендуемый порядок для следующего домена:

1. Добавить таблицы в `Database.init_schema()`.
2. Добавить методы чтения и записи в `Database`.
3. Добавить tests для методов базы.
4. Добавить keyboard/service, если нужна отдельная логика.
5. Добавить router в `app/handlers/`.
6. Подключить router в `app/handlers/__init__.py`.

Для ингредиентов использовать `app/services/ingredients.py`: этот парсер нужен не только рецептам, но и будущему списку покупок.
Для расчёта недель и будущего списка покупок использовать `app/services/menus.py`, где уже есть агрегация ингредиентов меню.

## Git

Перед изменениями:

```bash
git status -sb
```

Перед публикацией:

```bash
venv/bin/pytest
git status -sb
git log --oneline --decorate --max-count=5
git remote -v
```

Remote проекта:

```text
https://github.com/konstantin-fomin/FamilyMenuBot
```

Если обычный `git push` отклонен из-за credentials, не менять историю силой. Сначала проверить доступы и состояние remote.
