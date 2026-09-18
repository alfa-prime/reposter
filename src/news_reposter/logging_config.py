import logging
import logging.config
import time
from contextvars import ContextVar

request_id_context: ContextVar[str] = ContextVar("request_id", default="-")


def current_request_id() -> str:
    """Возвращает идентификатор текущего HTTP-запроса или прочерк вне запроса."""

    return request_id_context.get()


class RequestIdFilter(logging.Filter):
    """Добавляет request_id ко всем записям, включая фоновые задачи."""

    def filter(self, record: logging.LogRecord) -> bool:
        record.request_id = current_request_id()
        return True


class UTCFormatter(logging.Formatter):
    """Форматирует время логов в UTC для одинакового результата во всех средах."""

    converter = time.gmtime


def configure_logging(level: str = "INFO") -> None:
    """Настраивает единый stdout-формат приложения и Uvicorn."""

    normalized_level = level.upper()
    logging.config.dictConfig(
        {
            "version": 1,
            "disable_existing_loggers": False,
            "filters": {
                "request_id": {
                    "()": RequestIdFilter,
                },
            },
            "formatters": {
                "default": {
                    "()": UTCFormatter,
                    "format": (
                        "%(asctime)s %(levelname)s %(name)s "
                        "request_id=%(request_id)s %(message)s"
                    ),
                    "datefmt": "%Y-%m-%dT%H:%M:%SZ",
                },
            },
            "handlers": {
                "stdout": {
                    "class": "logging.StreamHandler",
                    "stream": "ext://sys.stdout",
                    "filters": ["request_id"],
                    "formatter": "default",
                },
            },
            "root": {
                "handlers": ["stdout"],
                "level": normalized_level,
            },
            "loggers": {
                "uvicorn": {
                    "handlers": ["stdout"],
                    "level": normalized_level,
                    "propagate": False,
                },
                "uvicorn.error": {
                    "handlers": ["stdout"],
                    "level": normalized_level,
                    "propagate": False,
                },
                # Доступ логируется middleware вместе с request_id. Стандартный
                # access-log Uvicorn иначе дублировал бы каждую запись.
                "uvicorn.access": {
                    "handlers": ["stdout"],
                    "level": "WARNING",
                    "propagate": False,
                },
            },
        }
    )
