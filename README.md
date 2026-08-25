# News Reposter

Первый этап проекта: получение последнего поста из группы VK через официальный метод `wall.get`.

## Настройка

```bash
uv sync
cp .env.example .env
```

Заполните `.env`:

```dotenv
VK_ACCESS_TOKEN=ваш_токен
VK_GROUP=https://vk.ru/news_murmansk
VK_API_VERSION=5.199
```

`VK_GROUP` принимает ссылку на `vk.ru` или `vk.com`, короткое имя группы,
`club123456` или числовой ID.

## Запуск

```bash
uv run uvicorn news_reposter.main:app --reload
```

Проверка приложения:

```bash
curl http://127.0.0.1:8000/health
```

Получение последнего поста группы из `.env`:

```bash
curl http://127.0.0.1:8000/api/v1/vk/posts/latest
```

Можно разово запросить другую публичную группу:

```bash
curl 'http://127.0.0.1:8000/api/v1/vk/posts/latest?group=https://vk.ru/another_group'
```

Интерактивная документация доступна по адресу <http://127.0.0.1:8000/docs>.

## Тесты

```bash
uv run pytest
```
