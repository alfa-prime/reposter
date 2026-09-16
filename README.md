# News Reposter

Сервис автоматически собирает новые публикации из VK, складывает их в
редакционную очередь и после модерации публикует в подключённые каналы MAX.
Прямой маршрут VK → MAX отключён: каждая публикация проходит через очередь и
сохраняется в истории.

## Что уже работает

- несколько VK-источников и несколько целевых каналов MAX;
- привязка источников к конкретным каналам;
- автоматический сбор по расписанию и ручной запуск из админки;
- загрузка всех записей, появившихся после последней сохранённой, включая
  объём больше одной страницы VK;
- редакционная очередь: текст, подпись, фотографии, видео, модерация и архив;
- немедленная и запланированная публикация в MAX;
- защита от одновременной повторной отправки одного поста;
- GigaChat-рерайт как необязательный инструмент редактора;
- PostgreSQL, Alembic, Docker Compose и web-интерфейс на React.

## Как работает сбор

При первом успешном обращении к новому источнику сервис сохраняет только его
последнюю незакреплённую запись. Это создаёт точку отсчёта и не заполняет
очередь всей историей сообщества.

При каждом следующем проходе сервис находит последний сохранённый ID и
загружает **все** более новые записи в хронологическом порядке. Если появилось
10, 150 или больше постов, клиент VK проходит нужное число страниц и не
ограничивается первыми 100 результатами.

По умолчанию сбор запускается каждые 15 минут с 08:00 до 20:00 по московскому
времени. Ручная кнопка и планировщик используют один и тот же сборщик и не
могут выполнять проход одновременно.

## Быстрый запуск в Docker

```bash
cp .env.example .env
docker compose up -d --build
docker compose ps
```

Админка будет доступна на порту, заданном через `HTTP_PORT` (по умолчанию 80),
API — внутри проекта на порту 8000. Перед стартом приложения контейнер
`migrate` ожидает PostgreSQL и применяет миграции Alembic.

Полезные команды:

```bash
docker compose logs -f app
docker compose down
docker compose -f compose.yaml up -d --build
```

Последняя команда запускает базовую конфигурацию без development override.

## Основные настройки

Сначала сгенерируйте ключ доступа к API:

```bash
python -c "import secrets; print(secrets.token_urlsafe(32))"
```

Минимальный `.env`:

```dotenv
API_KEY=сгенерированный_ключ

VK_ACCESS_TOKEN=сервисный_ключ_VK
VK_API_VERSION=5.199

MAX_ACCESS_TOKEN=токен_бота_MAX
MAX_API_URL=https://platform-api2.max.ru

POSTGRES_DB=news_reposter
POSTGRES_USER=news_reposter
POSTGRES_PASSWORD=news_reposter
POSTGRES_HOST=postgres
POSTGRES_PORT=5432

COLLECTION_ENABLED=true
COLLECTION_INTERVAL_MINUTES=15
COLLECTION_START_HOUR=8
COLLECTION_END_HOUR=20
COLLECTION_TIMEZONE=Europe/Moscow
```

Настройки расписания:

| Переменная | Назначение | Значение по умолчанию |
|---|---|---|
| `COLLECTION_ENABLED` | включает фоновый сбор | `true` |
| `COLLECTION_INTERVAL_MINUTES` | интервал между проходами | `15` |
| `COLLECTION_START_HOUR` | начало дневного окна | `8` |
| `COLLECTION_END_HOUR` | конец дневного окна | `20` |
| `COLLECTION_TIMEZONE` | часовой пояс расписания | `Europe/Moscow` |

`COLLECTION_END_HOUR` должен быть позже `COLLECTION_START_HOUR`. Значения
проверяются при запуске приложения.

## Подключение MAX

Канал добавляется в интерфейсе по публичной ссылке. Чтобы приложение узнало
его `chat_id`:

1. задайте `MAX_WEBHOOK_URL` и `MAX_WEBHOOK_SECRET`;
2. создайте подписку через `POST /api/v1/max/subscriptions/channel-discovery`;
3. добавьте бота в канал и назначьте администратором;
4. после webhook-события добавьте канал в разделе «Целевые каналы».

API MAX может требовать сертификаты Минцифры. Если они не установлены в
системное хранилище, положите объединённый PEM в `certs/` и задайте:

```dotenv
MAX_CA_FILE=/app/certs/russian-trusted-ca.pem
```

Файлы `certs/*.pem` не попадают в Git и Docker build context.

## GigaChat

Рерайт необязателен. Для него задаются `GIGACHAT_CREDENTIALS`,
`GIGACHAT_SCOPE`, `GIGACHAT_MODEL` и при необходимости `GIGACHAT_CA_FILE`.
Без credentials сбор, редактирование, модерация и публикация продолжают
работать; недоступна только генерация текста.

## API и ручной сбор

Все маршруты `/api/v1/*`, кроме webhook MAX с собственным секретом, защищены
заголовком `X-API-Key`. Health-check маршруты публичны:

```bash
curl http://127.0.0.1:8000/health
curl http://127.0.0.1:8000/health/database
```

Запустить тот же проход сборщика вне расписания:

```bash
curl -X POST \
  -H 'X-API-Key: ваш_ключ' \
  http://127.0.0.1:8000/api/v1/system/collect-now
```

Интерактивная документация: <http://127.0.0.1:8000/docs>.

## Локальная разработка

Backend:

```bash
uv sync --frozen
uv run uvicorn news_reposter.main:app --reload
```

Frontend:

```bash
cd frontend
npm ci
npm run dev
```

Vite проксирует `/api` и `/health` на `http://localhost:8000`.

## Проверки перед коммитом

```bash
uv run ruff check .
uv run ruff format --check .
uv run pytest --cov --cov-report=term-missing --cov-fail-under=60

cd frontend
npm ci
npm run build
```

CI выполняет те же проверки, проверяет полный цикл миграций
`upgrade → downgrade → upgrade` на PostgreSQL и собирает оба Docker-образа.

## Хранение данных

- `posts` — исходные публикации VK с уникальной парой
  `source_id + external_post_id`;
- `post_attachments` — фотографии и видео исходного поста;
- `queue_items` — отдельная редакционная версия для каждого целевого канала;
- `publications` — технический статус, число попыток и результат отправки;
- `data/media` — загруженные редактором фото, видео и порядок медиа.

Удаление элемента очереди, источника или канала также очищает связанные файлы
из `data/media`.
