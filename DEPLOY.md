# Развёртывание и обслуживание News Reposter

Документ описывает установку на сервер, безопасное обновление, резервное
копирование, восстановление и мониторинг. Рекомендуемая конфигурация: Ubuntu
24.04 LTS, 2 vCPU, 4 ГБ RAM и SSD от 40 ГБ.

## 1. Подготовка сервера

Установите Docker Engine, Docker Compose и Git:

```bash
docker --version
docker compose version
git --version
```

Для постоянной работы используйте домен и HTTPS. Откройте SSH, HTTP и HTTPS:

```bash
sudo ufw allow OpenSSH
sudo ufw allow 80/tcp
sudo ufw allow 443/tcp
sudo ufw enable
```

Клонируйте приватный репозиторий. На сервере должен быть настроен SSH-ключ с
доступом к GitHub:

```bash
git clone git@github.com:alfa-prime/reposter.git
cd reposter
git switch master
```

## 2. Настройка окружения

```bash
cp .env.example .env
chmod 600 .env
```

Как минимум задайте:

```dotenv
VK_ACCESS_TOKEN=токен_VK
MAX_ACCESS_TOKEN=токен_бота_MAX
POSTGRES_PASSWORD=длинный_случайный_пароль
SITE_ADDRESS=news.example.ru
AUTH_COOKIE_SECURE=true
```

Пароль PostgreSQL можно создать командой `openssl rand -hex 32`.

В production FastAPI доступен только во внутренней сети Docker. Caddy принимает
HTTP/HTTPS, автоматически получает TLS-сертификат и проксирует запросы в
приложение. Пользователей, роли, сессии, CSRF-защиту и ограничение попыток входа
обрабатывает само приложение.

Для короткой проверки без домена можно задать `SITE_ADDRESS=:80` и
`AUTH_COOKIE_SECURE=false`. Обычный HTTP не шифрует пароли и не подходит для
постоянной эксплуатации.

## 3. Первый запуск

```bash
docker compose -f compose.yaml -f compose.prod.yaml up -d --build
docker compose -f compose.yaml -f compose.prod.yaml ps
```

Контейнер `migrate` дождётся PostgreSQL и применит миграции Alembic до запуска
backend. Для новой базы создайте первого администратора:

```bash
docker compose -f compose.yaml -f compose.prod.yaml exec app \
  python -m news_reposter.cli create-admin
```

Проверьте приложение и базу:

```bash
curl --fail --silent https://news.example.ru/health
curl --fail --silent https://news.example.ru/health/database
docker compose -f compose.yaml -f compose.prod.yaml logs --tail=100 app
```

## 4. Безопасное обновление

Перед обновлением изменения должны пройти тесты и попасть в `master`:

```bash
cd /путь/к/reposter
./backup/run-backup.sh
git pull --ff-only origin master
docker compose -f compose.yaml -f compose.prod.yaml up -d --build
```

`--ff-only` запрещает неожиданное слияние истории на сервере. Docker собирает
новые образы, применяет миграции и заменяет изменившиеся контейнеры. `.env`,
PostgreSQL и постоянные Docker-тома не перезаписываются.

После обновления:

```bash
docker compose -f compose.yaml -f compose.prod.yaml ps
curl --fail --silent https://news.example.ru/health
curl --fail --silent https://news.example.ru/health/database
docker compose -f compose.yaml -f compose.prod.yaml logs --since 5m app migrate
systemctl start reposter-monitor.service
systemctl show reposter-monitor.service -p Result --value
```

Для отката выберите предыдущий исправный коммит и снова соберите контейнеры.
Если релиз менял схему или данные, сначала изучите миграцию Alembic — откатывать
базу вслепую нельзя.

## 5. Пул PostgreSQL

Один процесс приложения использует до 10 постоянных и до 10 временных
соединений:

```dotenv
DATABASE_POOL_SIZE=10
DATABASE_MAX_OVERFLOW=10
DATABASE_POOL_TIMEOUT_SECONDS=30
DATABASE_POOL_RECYCLE_SECONDS=1800
DATABASE_COMMAND_TIMEOUT_SECONDS=30
```

При добавлении процессов FastAPI или фоновых воркеров считайте суммарное число
соединений. Планировщики уже вынесены из FastAPI в отдельный сервис `scheduler`.
Расчёт для двух API-процессов и всех Celery-сервисов, а также проверка памяти
приведены в разделе «Бюджет при `API_WORKERS=2`» файла `BACKGROUND_TASKS.md`.

## 5.1. Ограничения медиа

Фото и видео загружаются потоком: приложение не хранит весь файл в памяти.
Перед записью проверяются размер материала, число вложений и свободное место.
Без необходимости значения по умолчанию менять не следует:

```dotenv
MEDIA_IMAGE_MAX_BYTES=10485760
MEDIA_VIDEO_MAX_BYTES=52428800
MEDIA_ITEM_MAX_BYTES=157286400
MEDIA_ITEM_MAX_ATTACHMENTS=12
MEDIA_MAX_CONCURRENT_UPLOADS=3
MEDIA_MIN_FREE_BYTES=5368709120
MEDIA_MIN_FREE_PERCENT=10
MEDIA_TEMP_MAX_AGE_HOURS=24
MEDIA_ORPHAN_MAX_AGE_DAYS=7
```

Сервис ежедневно удаляет незавершённые временные загрузки старше суток и
каталоги удалённых материалов, которые оставались без владельца более недели.

## 6. Зашифрованные резервные копии S3

Копия содержит согласованный дамп PostgreSQL и весь том с медиа. Restic шифрует
данные до отправки в приватный S3-бакет.

```dotenv
BACKUP_S3_ENDPOINT=https://s3.twcstorage.ru
BACKUP_S3_BUCKET=имя_бакета
BACKUP_S3_REGION=ru-1
BACKUP_S3_PREFIX=reposter
BACKUP_S3_ACCESS_KEY=ключ_доступа
BACKUP_S3_SECRET_KEY=секретный_ключ
RESTIC_PASSWORD=отдельный_длинный_пароль
BACKUP_HOST_NAME=reposter-production
BACKUP_KEEP_DAILY=14
BACKUP_KEEP_WEEKLY=8
BACKUP_KEEP_MONTHLY=6
BACKUP_CHECK_SUBSET=5%
```

Пароль Restic храните также вне сервера в менеджере паролей. Без него копии
невозможно восстановить.

```bash
./backup/run-backup.sh
docker compose -f compose.yaml -f compose.prod.yaml --profile backup \
  run --rm backup snapshots
./backup/run-verify.sh
```

По умолчанию сохраняются 14 ежедневных, 8 еженедельных и 6 ежемесячных
снимков. Проверка читает метаданные и меняющуюся выборку из 5% данных.

### Автоматическое расписание

```bash
PROJECT_DIR=/root/Code/reposter
sed "s|REPLACE_WITH_PROJECT_DIRECTORY|$PROJECT_DIR|g" \
  backup/reposter-backup.service | \
  sudo tee /etc/systemd/system/reposter-backup.service >/dev/null
sed "s|REPLACE_WITH_PROJECT_DIRECTORY|$PROJECT_DIR|g" \
  backup/reposter-backup-verify.service | \
  sudo tee /etc/systemd/system/reposter-backup-verify.service >/dev/null
sudo cp backup/reposter-backup.timer /etc/systemd/system/
sudo cp backup/reposter-backup-verify.timer /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now reposter-backup.timer reposter-backup-verify.timer
systemctl list-timers 'reposter-backup*'
```

Ежедневная копия создаётся примерно в 03:15 по времени сервера с небольшой
случайной задержкой. Проверка репозитория выполняется ежемесячно.

```bash
systemctl status reposter-backup.service
journalctl -u reposter-backup.service -n 100 --no-pager
systemctl status reposter-backup-verify.service
```

## 7. Проверка и полное восстановление

Сначала проверяйте восстановление на временном сервере. Полное восстановление
заменяет выбранную базу и все медиафайлы.

```bash
docker compose -f compose.yaml -f compose.prod.yaml --profile backup \
  run --rm backup snapshots
docker compose -f compose.yaml -f compose.prod.yaml stop frontend app
RESTORE_CONFIRM=RESTORE RESTORE_SNAPSHOT=latest \
  docker compose -f compose.yaml -f compose.prod.yaml --profile backup \
  run --rm -e RESTORE_CONFIRM -e RESTORE_SNAPSHOT backup restore
docker compose -f compose.yaml -f compose.prod.yaml run --rm migrate
docker compose -f compose.yaml -f compose.prod.yaml up -d app frontend
curl --fail --silent https://news.example.ru/health/database
```

Проводите проверку после изменения схемы резервирования и не реже одного раза
в три месяца. Записывайте дату, ID снимка, длительность и результат.

## 8. Мониторинг ntfy

Каждые пять минут сервер проверяет контейнеры, публичные health-check, заполнение
диска, свежесть копии и состояние задач резервирования. При изменении проблемы
приходит одно аварийное сообщение, после устранения — одно сообщение о
восстановлении. По понедельникам около 09:00 по Москве приходит обычная
недельная сводка: последняя копия, контейнеры, диск и состояние проверки S3.

```dotenv
NTFY_URL=https://ntfy.sh/длинная_случайная_тема
NTFY_TOKEN=
MONITOR_HEALTH_URL=https://news.example.ru/health
MONITOR_DATABASE_HEALTH_URL=https://news.example.ru/health/database
MONITOR_DISK_WARNING_PERCENT=75
MONITOR_BACKUP_MAX_AGE_HOURS=26
```

Для анонимной темы её имя является секретом. Подходит `reposter-` плюс результат
`openssl rand -hex 24`.

```bash
PROJECT_DIR=/root/Code/reposter
sed "s|REPLACE_WITH_PROJECT_DIRECTORY|$PROJECT_DIR|g" \
  monitoring/reposter-monitor.service | \
  sudo tee /etc/systemd/system/reposter-monitor.service >/dev/null
sudo cp monitoring/reposter-monitor.timer /etc/systemd/system/
sed "s|REPLACE_WITH_PROJECT_DIRECTORY|$PROJECT_DIR|g" \
  monitoring/reposter-weekly-summary.service | \
  sudo tee /etc/systemd/system/reposter-weekly-summary.service >/dev/null
sudo cp monitoring/reposter-weekly-summary.timer /etc/systemd/system/
sudo systemctl daemon-reload
set -a; . ./.env; set +a
./monitoring/notify-ntfy.sh \
  "News Reposter" "Тест уведомлений" default white_check_mark
sudo systemctl enable --now reposter-monitor.timer
sudo systemctl enable --now reposter-weekly-summary.timer
```

```bash
systemctl status reposter-monitor.service
systemctl list-timers reposter-monitor.timer
systemctl list-timers reposter-weekly-summary.timer
journalctl -u reposter-monitor.service -n 100 --no-pager
```

## 9. Постоянные данные

- `postgres_data` — PostgreSQL;
- `media_data` — изображения, видео, аватары и состояние медиа;
- `caddy_data` — TLS-сертификаты и данные Caddy;
- `.env` — секреты конкретного сервера;
- S3-бакет — зашифрованные внешние копии.

`docker compose down` не удаляет тома. Не используйте ключ `-v`, если не хотите
удалить постоянные данные.

## Рост журналов: миграция 0019

Миграция добавляет вычисляемый `audit_events.target_id` из исторического JSON
и индексы под сортировку и фильтры аудита и сборщика. ID канала сохраняется
после удаления канала; FK здесь намеренно нет. Вычисляемое поле работает и
для прежних версий приложения, которые записывают только `details`.
Некорректные и выходящие за диапазон integer исторические ID дают NULL.

На текущем малом объёме используется обычная транзакционная миграция.
`lock_timeout=2s` и `statement_timeout=30s` ограничивают ожидание блокировок
и время каждого SQL-запроса миграции. Если применение прервано, транзакция
откатывается; сначала устраните причину и повторите `migrate`.
Для больших таблиц требуется отдельное окно обслуживания либо поэтапное
добавление поля и построение индексов CONCURRENTLY.

Перед запуском новой версии убедитесь, что сервис `migrate` успешно завершился.
Стандартные зависимости Compose уже обеспечивают этот порядок.
Для отката сначала верните прежние app и frontend; только затем при необходимости
выполните `alembic downgrade 0018_publication_recovery`. JSON-история сохраняется.

Интерфейс трёх журналов использует `pagination=cursor` с `limit` до 100.
Ответ содержит `has_more` и `next_cursor`; `total=null`, обязательного COUNT нет.
Следующая страница передаёт полученный `cursor` вместе с прежними фильтрами.
Курсор включает время и ID для аудита, ID для запусков; время сохраняет микросекунды.
Это последовательный просмотр истории, а не фиксированный снимок транзакции:
обновление возвращает к первой странице, новые события отображаются после обновления.
Интерфейс показывает номер страницы и диапазон без общего числа страниц.
Смена фильтров или размера страницы сбрасывает историю переходов; устаревшие
запросы отменяются и не подменяют текущую страницу.

Режим `pagination=offset` остаётся режимом API по умолчанию с числовым `total`.
OFFSET ограничен 10 000; более глубокий просмотр нужно перевести на курсор.
Смешение режимов, повреждённый курсор и курсор с другими фильтрами дают 422.

`DATABASE_JOURNAL_TIMEOUT_SECONDS` (по умолчанию 5) устанавливает локальный
PostgreSQL statement_timeout для запросов списка журналов. Отмена долгого SQL
или таймаут драйвера/пула возвращает 503; транзакция откатывается.
При следующем запросе таймаут не остаётся в соединении пула. Настройка не меняет
таймауты фонового сбора и публикации; это лимит SQL, а не всего HTTP-запроса.

Проверки: `RUN_POSTGRES_TESTS=1 uv run pytest tests/test_journal_postgres.py`
на отдельной тестовой БД. Тест миграции выполняет downgrade/upgrade, поэтому
его нельзя запускать с подключением к продовой базе.

Воспроизводимый замер на синтетических 100 000 событий и 50 000 запусков:
задайте `JOURNAL_BENCHMARK_DATABASE_URL` для отдельной БД с миграциями и выполните
`uv run python scripts/check_journal_growth.py`. Скрипт откатывает тестовые строки,
но ANALYZE и продвижение sequences могут оставить служебные изменения;
используйте только одноразовую БД. Времена локальной машины не являются SLA прода.


## Фоновые задачи (этап 5)

Инструкция включения, наблюдения и отката: [BACKGROUND_TASKS.md](BACKGROUND_TASKS.md).
После включения использовать `compose.tasks.yaml` и профиль `background` вместе
с основными compose файлами при обновлении app и task workers. Все исполнители
используют образ `reposter-app`; после сборки app их нужно пересоздать.
Обычный запуск без файла задач отключает производителей и оставляет worker-контейнеры
вне выбранной конфигурации — для отката их остановить явно после завершения задач.
Для отката исполнения миграцию `0020_background_tasks` не понижать: она содержит
историю и ключи дедупликации. Инструкция отката журнала выше относится к этапу 4.
