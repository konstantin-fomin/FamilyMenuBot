# AGENTS.md

Краткий контекст для будущей работы Codex в этом репозитории.

## Проект

Семейный Telegram-бот на Python и aiogram 3.x. Сейчас реализованы доступ по приглашениям, раздел семьи, раздел рецептов и заглушки будущих разделов меню недели/покупок.

## Важные команды

```bash
venv/bin/python bot.py
docker compose up -d --build
docker compose logs -f family-menu-bot
venv/bin/pytest
venv/bin/python -m py_compile bot.py app/config.py app/database/storage.py app/handlers/start.py app/handlers/family.py app/handlers/menu.py
```

## Важные файлы

- `bot.py` - entrypoint.
- `app/config.py` - `.env`, `BOT_TOKEN`, путь к базе.
- `app/database/storage.py` - SQLite-схема и доступ к данным.
- `app/handlers/start.py` - `/start`, owner/member flow.
- `app/handlers/family.py` - список семьи и приглашения.
- `app/handlers/recipes.py` - рецепты, FSM добавления/редактирования, просмотр и удаление.
- `app/keyboards/` - Telegram-клавиатуры.
- `app/texts.py` - единый источник текстов кнопок и общих ответов.
- `app/services/ingredients.py` - парсер и нормализация ингредиентов.
- `app/middlewares/logging.py` - логирование входящих событий и ошибок.
- `tests/` - тесты базы и приглашений.
- `Dockerfile`, `docker-compose.yml`, `.dockerignore` - контейнерный запуск.

## Инварианты

- Не перезаписывать и не коммитить `.env`.
- Не коммитить `venv/`, `data/`, кэши Python и pytest.
- Не коммитить `logs/`.
- Все тексты бота должны быть на русском.
- Первый пользователь становится `owner`.
- Остальные без валидного приглашения получают отказ.
- Приглашения одноразовые.
- Все пользователи сейчас относятся к одной семье; multi-family пока нет.

## Стиль изменений

- Сохранять модульную структуру `handlers`, `database`, `keyboards`, `services`.
- Не добавлять фреймворки и тяжелые зависимости без явной необходимости.
- Для новой логики сначала расширять тесты.
- Перед коммитом запускать `venv/bin/pytest`.
- Перед публикацией проверять `git status -sb` и remote.

## Документация

Подробности:

- `README.md` - запуск и обзор.
- `docs/ARCHITECTURE.md` - устройство проекта.
- `docs/DEVELOPMENT.md` - процесс разработки.
