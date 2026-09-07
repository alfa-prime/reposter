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
API_KEY=сгенерированный_ключ_доступа

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
добавить в системное хранилище, сохраните объединённый PEM-файл в каталоге
`certs`, например `certs/russian-trusted-ca.pem`, и укажите путь внутри
контейнера:

```dotenv
MAX_CA_FILE=/app/certs/russian-trusted-ca.pem
```

Файлы `*.pem` из этого каталога исключены из Git и контекста сборки Docker.

## Доступ к API

Все прикладные маршруты `/api/v1/*` защищены API-ключом. Сгенерировать ключ
можно локально:

```bash
python -c "import secrets; print(secrets.token_urlsafe(32))"
```

Полученное значение сохраните в `API_KEY` файла `.env` и передавайте в
заголовке `X-API-Key`:

```bash
curl -H 'X-API-Key: ваш_ключ' http://127.0.0.1:8000/api/v1/sources
```

В Swagger UI откройте <http://127.0.0.1:8000/docs>, нажмите `Authorize` и
введите сам ключ без префиксов. Маршруты `/health` и `/health/database`
остаются доступными без ключа для проверок состояния приложения и Docker.

## Запуск в Docker

Для локальной разработки запустите весь проект одной командой:

```bash
docker compose up -d --build
docker compose ps
```

Docker Compose автоматически объединяет `compose.yaml` и
`compose.override.yaml`. В режиме разработки исходный код подключается в
контейнер, а Uvicorn запускается с автоматической перезагрузкой.

Перед запуском приложения отдельный контейнер `migrate` ожидает готовности
PostgreSQL и применяет миграции Alembic. Приложение внутри Docker подключается к
базе по имени сервиса `postgres` и внутреннему порту `5432`.

Логи приложения:

```bash
docker compose logs -f app
```

Остановка контейнеров без удаления данных:

```bash
docker compose down
```

Для запуска без настроек разработки используйте только базовый файл:

```bash
docker compose -f compose.yaml up -d --build
```

Приложение использует асинхронный драйвер `asyncpg`, асинхронные сессии
SQLAlchemy и асинхронное окружение Alembic. Строка подключения собирается в
`config.py` из отдельных параметров `POSTGRES_*`.

Связь приложения с базой можно проверить через HTTP:

```bash
curl http://127.0.0.1:8000/health/database
```

Успешный ответ:

```json
{"status":"ok","database":"connected"}
```

Первая миграция создаёт таблицу `sources`. В ней хранятся название источника,
тип платформы, ссылка и признак активности. Неактивный источник сохраняется в
базе, но будущий сборщик публикаций не будет его опрашивать.

## Источники

Создание источника:

```bash
curl -X POST http://127.0.0.1:8000/api/v1/sources \
  -H 'X-API-Key: ваш_ключ' \
  -H 'Content-Type: application/json' \
  -d '{"name":"Полуостров 51","platform":"vk","url":"https://vk.ru/peninsula51"}'
```

Получение списка:

```bash
curl -H 'X-API-Key: ваш_ключ' http://127.0.0.1:8000/api/v1/sources
```

Список поддерживает параметры `platform`, `is_active`, `offset` и `limit`.
Получение, частичное изменение и удаление одной записи выполняются по адресу
`/api/v1/sources/{source_id}` методами `GET`, `PATCH` и `DELETE`.

## Цели публикаций

Цель хранит платформу и внешний идентификатор канала. Для MAX это значение
`MAX_CHAT_ID`; токен бота остаётся в `.env` и в базу не записывается.

```bash
curl -X POST http://127.0.0.1:8000/api/v1/targets \
  -H 'X-API-Key: ваш_ключ' \
  -H 'Content-Type: application/json' \
  -d '{"name":"Новости 51 региона","platform":"max","external_id":"-77162942582085","url":"https://max.ru/channel_51_news"}'
```

Получение списка:

```bash
curl -H 'X-API-Key: ваш_ключ' http://127.0.0.1:8000/api/v1/targets
```

Список поддерживает параметры `platform`, `is_active`, `offset` и `limit`.
Получение, частичное изменение и удаление одной цели выполняются по адресу
`/api/v1/targets/{target_id}` методами `GET`, `PATCH` и `DELETE`.

## Модель очереди постов

Таблица `posts` хранит исходный и переписанный текст, статус обработки, ссылку
на оригинал, исходный JSON и связь с `sources`. Пара `source_id` и
`external_post_id` уникальна, поэтому один пост нельзя получить дважды.

Таблица `post_attachments` хранит фотографии, видео и остальные вложения в
исходном порядке. При удалении поста его вложения удаляются автоматически.

Таблица `publications` связывает пост с одной записью из `targets`. Для каждой
цели отдельно сохраняются статус отправки, число попыток, ошибка, ID и ссылка
опубликованного сообщения. Один пост может иметь несколько публикаций.

Статусы обработки поста:

```text
received → rewriting → rewritten → awaiting_moderation → approved
                                                   └──→ rejected
```

При ошибке обработки пост получает статус `failed`. Публикация проходит свои
состояния: `pending`, `publishing`, `published` или `failed`.

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
curl -H 'X-API-Key: ваш_ключ' \
  http://127.0.0.1:8000/api/v1/vk/posts/latest
```

Публикация последнего поста VK в настроенный канал MAX:

```bash
curl -X POST \
  -H 'X-API-Key: ваш_ключ' \
  http://127.0.0.1:8000/api/v1/max/posts/from-vk/latest
```

Другую публичную группу можно передать в параметре `group`:

```bash
curl -X POST \
  -H 'X-API-Key: ваш_ключ' \
  'http://127.0.0.1:8000/api/v1/max/posts/from-vk/latest?group=https://vk.ru/another_group'
```

Интерактивная документация доступна по адресу <http://127.0.0.1:8000/docs>.

## Тесты

```bash
uv run pytest
```
