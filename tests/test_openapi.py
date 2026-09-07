from news_reposter.main import app


EXPECTED_OPERATIONS = {
    ("/health", "get"): "Проверить работу приложения",
    ("/health/database", "get"): "Проверить подключение к PostgreSQL",
    ("/api/v1/vk/posts/latest", "get"): "Получить последний пост VK",
    (
        "/api/v1/max/posts/from-vk/latest",
        "post",
    ): "Опубликовать последний пост VK в MAX",
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
}


def test_openapi_has_russian_operation_descriptions() -> None:
    """Проверяет русские заголовки и описания всех прикладных эндпоинтов."""

    schema = app.openapi()

    for (path, method), summary in EXPECTED_OPERATIONS.items():
        operation = schema["paths"][path][method]
        assert operation["summary"] == summary
        assert operation["description"]
        assert any("а" <= char.lower() <= "я" for char in operation["description"])


def test_openapi_has_ordered_russian_tags() -> None:
    """Проверяет названия и пояснения разделов Swagger."""

    tags = app.openapi()["tags"]

    assert [tag["name"] for tag in tags] == [
        "Система",
        "Источники",
        "Цели публикаций",
        "VK",
        "MAX",
    ]
    assert all(tag["description"] for tag in tags)


def test_openapi_models_have_field_descriptions() -> None:
    """Проверяет пояснения основных полей запросов в Swagger."""

    schemas = app.openapi()["components"]["schemas"]

    for schema_name in ("SourceCreate", "TargetCreate"):
        properties = schemas[schema_name]["properties"]
        assert all(
            property_schema.get("description")
            for property_schema in properties.values()
        )
