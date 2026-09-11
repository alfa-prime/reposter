from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, model_validator


class TargetSourceCreate(BaseModel):
    """Данные для подключения источника к целевому каналу."""

    source_id: int = Field(
        gt=0,
        description="Идентификатор источника в нашей базе",
        examples=[1],
    )
    is_active: bool = Field(
        default=True,
        description="Использовать ли источник при наполнении этого канала",
    )
    rewrite_enabled: bool = Field(
        default=True,
        description="Переписывать ли посты этого источника перед публикацией",
    )


class TargetSourceUpdate(BaseModel):
    """Изменяемые настройки источника внутри целевого канала."""

    is_active: bool | None = Field(
        default=None,
        description="Включить или отключить источник для этого канала",
    )
    rewrite_enabled: bool | None = Field(
        default=None,
        description="Включить или отключить рерайт постов этого источника",
    )

    @model_validator(mode="after")
    def validate_changes(self) -> "TargetSourceUpdate":
        """Проверяет, что запрос содержит хотя бы одно изменение."""

        if not self.model_fields_set:
            raise ValueError("нужно передать хотя бы одно поле")
        if any(getattr(self, field) is None for field in self.model_fields_set):
            raise ValueError("поля настроек источника не могут быть null")
        return self


class TargetSourceRead(BaseModel):
    """Источник, подключённый к конкретному целевому каналу."""

    model_config = ConfigDict(from_attributes=True)

    target_source_id: int = Field(description="Идентификатор связи в нашей базе")
    target_id: int = Field(description="Идентификатор целевого канала")
    source_id: int = Field(description="Идентификатор источника")
    is_active: bool = Field(description="Используется ли источник этим каналом")
    rewrite_enabled: bool = Field(
        description="Нужно ли переписывать посты этого источника"
    )
    created_at: datetime = Field(description="Дата и время подключения источника")
    updated_at: datetime = Field(description="Дата и время последнего изменения")
