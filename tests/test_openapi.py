from news_reposter.main import app

EXPECTED_OPERATIONS = {
    ("/api/v1/auth/login", "post"): "Войти в приложение",
    ("/api/v1/auth/me", "get"): "Получить текущего пользователя",
    ("/api/v1/auth/logout", "post"): "Выйти из текущей сессии",
    ("/api/v1/auth/logout-all", "post"): "Завершить все свои сессии",
    ("/api/v1/auth/change-password", "post"): "Сменить свой пароль",
    ("/health", "get"): "Проверить работу приложения",
    ("/health/database", "get"): "Проверить подключение к PostgreSQL",
    ("/api/v1/system/collect-now", "post"): "Запустить сбор источников сейчас",
    ("/api/v1/vk/posts/latest", "get"): "Получить последний пост VK",
    ("/api/v1/sources", "post"): "Добавить источник",
    ("/api/v1/sources", "get"): "Получить список источников",
    ("/api/v1/sources/{source_id}", "get"): "Получить источник",
    ("/api/v1/sources/{source_id}", "patch"): "Изменить источник",
    ("/api/v1/sources/{source_id}", "delete"): "Удалить источник",
    ("/api/v1/targets", "post"): "Добавить цель публикации",
    ("/api/v1/targets", "get"): "Получить список целей",
    ("/api/v1/targets/{target_id}", "get"): "Получить цель публикации",
    ("/api/v1/targets/{target_id}", "patch"): "Изменить цель публикации",
    ("/api/v1/targets/{target_id}", "delete"): "Удалить цель публикации",
    (
        "/api/v1/targets/{target_id}/sources",
        "post",
    ): "Подключить источник к целевому каналу",
    (
        "/api/v1/targets/{target_id}/sources",
        "get",
    ): "Получить источники целевого канала",
    (
        "/api/v1/targets/{target_id}/sources/{target_source_id}",
        "patch",
    ): "Изменить настройки источника целевого канала",
    (
        "/api/v1/targets/{target_id}/sources/{target_source_id}",
        "delete",
    ): "Отключить источник от целевого канала",
    ("/api/v1/queue", "post"): "Добавить пост в очередь",
    ("/api/v1/queue", "get"): "Получить очередь постов",
    ("/api/v1/queue/{queue_item_id}", "get"): "Получить элемент очереди",
    ("/api/v1/queue/{queue_item_id}", "patch"): "Изменить текст элемента очереди",
    ("/api/v1/queue/{queue_item_id}", "delete"): "Удалить элемент очереди",
    ("/api/v1/queue/{queue_item_id}/submit", "post"): "Отправить пост на модерацию",
    ("/api/v1/queue/{queue_item_id}/approve", "post"): "Одобрить пост",
    ("/api/v1/queue/{queue_item_id}/reject", "post"): "Отклонить пост",
    ("/api/v1/queue/{queue_item_id}/reopen", "post"): "Вернуть пост в работу",
    ("/api/v1/queue/{queue_item_id}/schedule", "post"): "Запланировать публикацию",
    ("/api/v1/queue/{queue_item_id}/publish-now", "post"): "Опубликовать пост сейчас",
}

SCHEDULER_READ_OPERATIONS = {
    ("/api/v1/system/collection/settings", "get"),
    ("/api/v1/system/collection/status", "get"),
    ("/api/v1/system/collection/runs", "get"),
    ("/api/v1/system/collection/runs/{run_id}", "get"),
}

QUEUE_READ_OPERATIONS = {
    ("/api/v1/queue", "get"),
    ("/api/v1/queue/page", "get"),
    ("/api/v1/queue/{queue_item_id}", "get"),
    ("/api/v1/queue/{queue_item_id}/media-state", "get"),
    ("/api/v1/queue/{queue_item_id}/media/{media_id}", "get"),
    ("/api/v1/queue/{queue_item_id}/video-info", "get"),
    ("/api/v1/queue/{queue_item_id}/video/{media_id}", "get"),
}

QUEUE_WRITE_OPERATIONS = {
    ("/api/v1/queue", "post"),
    ("/api/v1/queue/{queue_item_id}", "patch"),
    ("/api/v1/queue/{queue_item_id}", "delete"),
    ("/api/v1/queue/{queue_item_id}/media", "post"),
    ("/api/v1/queue/{queue_item_id}/media/{media_id}", "delete"),
    ("/api/v1/queue/{queue_item_id}/media-state", "put"),
    ("/api/v1/queue/{queue_item_id}/video", "post"),
    ("/api/v1/queue/{queue_item_id}/video/{media_id}", "delete"),
    ("/api/v1/queue/{queue_item_id}/rewrite", "post"),
    ("/api/v1/queue/{queue_item_id}/submit", "post"),
    ("/api/v1/queue/{queue_item_id}/approve", "post"),
    ("/api/v1/queue/{queue_item_id}/reject", "post"),
    ("/api/v1/queue/{queue_item_id}/reopen", "post"),
    ("/api/v1/queue/{queue_item_id}/schedule", "post"),
    ("/api/v1/queue/{queue_item_id}/publish-now", "post"),
}

DIRECTORY_READ_OPERATIONS = {
    ("/api/v1/sources", "get"),
    ("/api/v1/sources/{source_id}", "get"),
    ("/api/v1/targets", "get"),
    ("/api/v1/targets/{target_id}", "get"),
    ("/api/v1/targets/{target_id}/sources", "get"),
}

DIRECTORY_MANAGE_OPERATIONS = {
    ("/api/v1/sources", "post"),
    ("/api/v1/sources/{source_id}", "patch"),
    ("/api/v1/sources/{source_id}", "delete"),
    ("/api/v1/targets", "post"),
    ("/api/v1/targets/{target_id}", "patch"),
    ("/api/v1/targets/{target_id}", "delete"),
    ("/api/v1/targets/{target_id}/sources", "post"),
    ("/api/v1/targets/{target_id}/sources/{target_source_id}", "patch"),
    ("/api/v1/targets/{target_id}/sources/{target_source_id}", "delete"),
}


def test_openapi_has_russian_operation_descriptions() -> None:
    """Проверяет русские заголовки и описания всех прикладных эндпоинтов."""

    schema = app.openapi()

    for (path, method), summary in EXPECTED_OPERATIONS.items():
        operation = schema["paths"][path][method]
        assert operation["summary"] == summary
        assert operation["description"]
        assert any("а" <= char.lower() <= "я" for char in operation["description"])


def test_openapi_does_not_expose_direct_vk_to_max_publication() -> None:
    """Любая отправка в MAX проходит только через редакционную очередь."""

    assert "/api/v1/max/posts/from-vk/latest" not in app.openapi()["paths"]


def test_openapi_has_ordered_russian_tags() -> None:
    """Проверяет названия и пояснения разделов Swagger."""

    tags = app.openapi()["tags"]

    assert [tag["name"] for tag in tags] == [
        "Авторизация",
        "Планировщик сбора",
        "Система",
        "Источники",
        "Цели публикаций",
        "Источники целевого канала",
        "Очередь постов",
        "VK",
        "MAX",
    ]
    assert all(tag["description"] for tag in tags)


def test_openapi_models_have_field_descriptions() -> None:
    """Проверяет пояснения основных полей запросов в Swagger."""

    schemas = app.openapi()["components"]["schemas"]

    for schema_name in (
        "SourceCreate",
        "TargetCreate",
        "TargetSourceCreate",
        "QueueItemCreate",
    ):
        properties = schemas[schema_name]["properties"]
        assert all(
            property_schema.get("description")
            for property_schema in properties.values()
        )


def test_openapi_describes_api_security_boundaries() -> None:
    """Разделяет API-key, публичный вход и пользовательскую сессию."""

    schema = app.openapi()
    security_scheme = schema["components"]["securitySchemes"]["APIKeyHeader"]
    session_scheme = schema["components"]["securitySchemes"]["SessionCookie"]

    assert security_scheme["type"] == "apiKey"
    assert security_scheme["in"] == "header"
    assert security_scheme["name"] == "X-API-Key"
    assert session_scheme == {
        "type": "apiKey",
        "description": "Непрозрачный токен серверной пользовательской сессии.",
        "in": "cookie",
        "name": "__Host-rp_session",
    }

    for path, path_item in schema["paths"].items():
        for method, operation in path_item.items():
            if path in {"/api/v1/max/webhook", "/api/v1/auth/login"}:
                assert "security" not in operation
            elif path.startswith("/api/v1/auth/"):
                assert operation["security"] == [{"SessionCookie": []}]
                assert "401" in operation["responses"]
                if method == "post":
                    assert "403" in operation["responses"]
            elif (path, method) in (
                SCHEDULER_READ_OPERATIONS
                | QUEUE_READ_OPERATIONS
                | QUEUE_WRITE_OPERATIONS
                | DIRECTORY_READ_OPERATIONS
                | DIRECTORY_MANAGE_OPERATIONS
            ):
                assert operation["security"] == [{"SessionCookie": []}]
                assert "401" in operation["responses"]
                assert "403" in operation["responses"]
                assert operation["responses"].get("503", {}).get("description") != (
                    "API-ключ не настроен на сервере"
                )
            elif path.startswith("/api/v1/"):
                assert operation["security"] == [{"APIKeyHeader": []}]
                assert "401" in operation["responses"]
                assert "503" in operation["responses"]
            elif path.startswith("/health"):
                assert "security" not in operation


def test_openapi_documents_csrf_header_for_auth_mutations() -> None:
    """Показывает frontend обязательный заголовок изменяющих auth-запросов."""

    schema = app.openapi()
    for path in (
        "/api/v1/auth/change-password",
        "/api/v1/auth/logout",
        "/api/v1/auth/logout-all",
    ):
        parameters = schema["paths"][path]["post"]["parameters"]
        assert any(
            parameter["in"] == "header" and parameter["name"] == "X-CSRF-Token"
            for parameter in parameters
        )


def test_openapi_documents_csrf_header_for_directory_mutations() -> None:
    """Документирует CSRF-заголовок операций управления справочниками."""

    schema = app.openapi()
    for path, method in DIRECTORY_MANAGE_OPERATIONS:
        parameters = schema["paths"][path][method]["parameters"]
        assert any(
            parameter["in"] == "header" and parameter["name"] == "X-CSRF-Token"
            for parameter in parameters
        )


def test_openapi_documents_csrf_header_for_queue_mutations() -> None:
    """Документирует CSRF-заголовок всех изменяющих операций очереди."""

    schema = app.openapi()
    for path, method in QUEUE_WRITE_OPERATIONS:
        parameters = schema["paths"][path][method]["parameters"]
        assert any(
            parameter["in"] == "header" and parameter["name"] == "X-CSRF-Token"
            for parameter in parameters
        )
