from news_reposter.main import app


def test_openapi_contains_russian_descriptions() -> None:
    """Проверяет, что основные эндпоинты документированы для Swagger UI."""

    schema = app.openapi()
    paths = schema["paths"]

    expected_summaries = {
        ("/api/v1/sources", "get"): "Получить список источников",
        ("/api/v1/sources", "post"): "Создать источник",
        ("/api/v1/targets", "get"): "Получить список целевых каналов",
        ("/api/v1/targets", "post"): "Создать целевой канал",
        ("/api/v1/queue", "get"): "Получить очередь постов",
        ("/api/v1/queue", "post"): "Добавить пост в очередь",
    }

    for (path, method), summary in expected_summaries.items():
        operation = paths[path][method]
        assert operation["summary"] == summary
        assert operation.get("description")


def test_openapi_groups_are_documented() -> None:
    """Проверяет понятные описания основных Swagger-разделов."""

    tags = {tag["name"]: tag["description"] for tag in app.openapi()["tags"]}

    assert "Система" in tags
    assert "Источники" in tags
    assert "Цели публикаций" in tags
    assert "Источники целевого канала" in tags
    assert "Очередь постов" in tags
    assert "VK" in tags
    assert "MAX" in tags
    assert all(description for description in tags.values())


def test_openapi_models_have_field_descriptions() -> None:
    """Проверяет описания полей ключевых входных схем."""

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


def test_openapi_describes_api_key_security() -> None:
    """Проверяет схему ключа и защиту рабочих эндпоинтов кроме публичного webhook."""

    schema = app.openapi()
    security_scheme = schema["components"]["securitySchemes"]["APIKeyHeader"]

    assert security_scheme["type"] == "apiKey"
    assert security_scheme["in"] == "header"
    assert security_scheme["name"] == "X-API-Key"

    for path, path_item in schema["paths"].items():
        for operation in path_item.values():
            if path == "/api/v1/max/webhook":
                assert "security" not in operation
            elif path.startswith("/api/v1/"):
                assert operation["security"] == [{"APIKeyHeader": []}]
                assert "401" in operation["responses"]
                assert "503" in operation["responses"]
            elif path.startswith("/health"):
                assert "security" not in operation
