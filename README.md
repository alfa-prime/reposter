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
```

`VK_GROUP` принимает ссылку на `vk.ru` или `vk.com`, короткое имя группы,
`club123456` или числовой ID.

API MAX использует сертификат Минцифры. На сервере должны быть установлены
`Russian Trusted Root CA` и `Russian Trusted Sub CA`. Если сертификаты нельзя
добавить в системное хранилище, укажите путь к PEM-файлу в `MAX_CA_FILE`.

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
