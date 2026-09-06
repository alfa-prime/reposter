# News Reposter

Сервис получает последний обычный пост из группы VK и публикует его вместе с
фотографиями в канал MAX.

## Настройка

```bash
uv sync
cp .env.example .env
```

Заполните `.env`:

```dotenv
VK_ACCESS_TOKEN=ваш_сервисный_ключ
VK_GROUP=https://vk.ru/peninsula51
VK_API_VERSION=5.199

MAX_ACCESS_TOKEN=токен_бота
MAX_CHAT_ID=-77162942582085
MAX_API_URL=https://platform-api2.max.ru

POSTGRES_DB=news_reposter
POSTGRES_USER=news_reposter
POSTGRES_PASSWORD=news_reposter
POSTGRES_HOST=localhost
POSTGRES_PORT=5432
DATABASE_ECHO=false
```

`VK_GROUP` принимает ссылку на `vk.ru` или `vk.com`, короткое имя группы,
`club123456` или числовой ID.

API MAX использует сертификат Минцифры. На сервере должны быть установлены
`Russian Trusted Root CA` и `Russian Trusted Sub CA`. Если сертификаты нельзя
добавить в системное хранилище, укажите путь к PEM-файлу в `MAX_CA_FILE`.

## PostgreSQL

Запустите базу данных:

```bash
docker compose up -d postgres
docker compose ps
```

Приложение использует асинхронный драйвер `asyncpg`, асинхронные сессии
SQLAlchemy и асинхронное окружение Alembic. Строка подключения собирается в
`config.py` из отдельных параметров `POSTGRES_*`. При запуске приложения на
хосте используйте `POSTGRES_HOST=localhost`; внутри Docker-сети —
`POSTGRES_HOST=postgres`.

Проверка подключения и применение миграций:

```bash
uv run alembic upgrade head
```

После запуска приложения связь с базой можно проверить через HTTP:

```bash
curl http://127.0.0.1:8000/health/database
```

Успешный ответ:

```json
{"status":"ok","database":"connected"}
```

На этом этапе каталог миграций пуст. Первая миграция появится после добавления
ORM-моделей источников и очереди публикаций.

## Запуск

```bash
uv run uvicorn news_reposter.main:app --reload
```

Проверка приложения:

```bash
curl http://127.0.0.1:8000/health
```

Получение последнего поста VK без публикации:

```bash
curl http://127.0.0.1:8000/api/v1/vk/posts/latest
```

Публикация последнего поста VK в настроенный канал MAX:

```bash
curl -X POST http://127.0.0.1:8000/api/v1/max/posts/from-vk/latest
```

Другую публичную группу можно передать в параметре `group`:

```bash
curl -X POST \
  'http://127.0.0.1:8000/api/v1/max/posts/from-vk/latest?group=https://vk.ru/another_group'
```

Интерактивная документация доступна по адресу <http://127.0.0.1:8000/docs>.

## Тесты

```bash
uv run pytest
```
