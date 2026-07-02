# FamilyMenuBot

Telegram-бот для семейного планирования меню, рецептов и списка покупок.

Работают регистрация владельца, доступ по одноразовым приглашениям, главное меню, раздел семьи, раздел рецептов и меню недели. Раздел покупок пока отвечает заглушкой.

## Возможности

- Первый пользователь, отправивший `/start`, становится владельцем семьи.
- Владелец может открыть «👨‍👩‍👧 Семья» и создать одноразовую ссылку-приглашение.
- Пользователь, вошедший по приглашению, становится участником семьи.
- Пользователи без приглашения получают отказ: «Это семейный бот. Попросите приглашение у владельца».
- Все участники видят общий список семьи.
- В разделе «📚 Рецепты» можно добавлять, смотреть, редактировать и удалять общие семейные рецепты.
- Ингредиенты парсятся из свободного списка и нормализуются по единицам: кг в г, л в мл.
- В разделе «📅 Меню недели» можно собрать меню текущей или следующей недели из рецептов.
- База данных хранится в SQLite: `data/bot.db`.
- Входящие сообщения, нажатия inline-кнопок и ошибки пишутся в `logs/bot.log`.

## Структура проекта

```text
.
├── bot.py                  # Точка входа
├── app/
│   ├── config.py           # Загрузка .env и общие настройки
│   ├── database/           # SQLite-слой и модели данных
│   ├── handlers/           # Aiogram-хендлеры
│   ├── keyboards/          # Reply/inline клавиатуры
│   └── services/           # Небольшие доменные helpers
├── tests/                  # Pytest-тесты
├── logs/                   # Локальные логи, не коммитятся
├── docs/                   # Техническая документация
├── requirements.txt
└── pytest.ini
```

## Настройка

Файл `.env` должен лежать в корне проекта и содержать:

```env
BOT_TOKEN=1234567890:telegram-bot-token
```

`.env` не коммитится. База `data/bot.db` тоже не коммитится.
Логи `logs/bot.log` создаются автоматически и не коммитятся.

## Установка

```bash
python3 -m venv venv
venv/bin/pip install -r requirements.txt
```

## Запуск

```bash
venv/bin/python bot.py
```

При первом запуске бот создаст папку `data/` и SQLite-базу `data/bot.db`.

## Docker

Сборка и запуск:

```bash
docker compose up -d --build
```

Остановка:

```bash
docker compose down
```

Перезапуск:

```bash
docker compose restart family-menu-bot
```

Логи:

```bash
docker compose logs -f family-menu-bot
```

Контейнер использует `.env` через `env_file`; сам `.env` не попадает в Docker image. Папки `data/` и `logs/` смонтированы с хоста в `/app/data` и `/app/logs`, поэтому база и логи переживают пересборку контейнера.

## Проверки

```bash
venv/bin/pytest
venv/bin/python -m py_compile bot.py app/config.py app/database/storage.py app/handlers/start.py app/handlers/family.py app/handlers/menu.py
venv/bin/python -c "import bot; from app.config import load_config; cfg = load_config(); assert cfg.bot_token"
```

## Документация

- [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) - устройство проекта и поток данных.
- [docs/DEVELOPMENT.md](docs/DEVELOPMENT.md) - правила разработки, тестирования и Git.
- [AGENTS.md](AGENTS.md) - краткий контекст для будущих агентных правок.
