import json
import logging
import os
import sys
from typing import Dict, Any

import structlog

ENVIRONMENT_ID = os.environ.get("ENVIRONMENT_ID", "local")  # staging, production, set by gitlab ci
SERVICE_NAME = "holi-okuna"

LABELS = {"environment": ENVIRONMENT_ID, "service": SERVICE_NAME}

_shared_processors = [
    structlog.contextvars.merge_contextvars,
    structlog.processors.TimeStamper(fmt="iso"),
    structlog.stdlib.add_logger_name,
    structlog.stdlib.add_log_level,
    structlog.stdlib.PositionalArgumentsFormatter(),
    structlog.processors.StackInfoRenderer(),
    structlog.processors.format_exc_info,
    structlog.processors.UnicodeDecoder(),
]


def normalize_severity_from_loglevel(level: str) -> int:
    gcloud_severities = {
        "critical": 600,
        "exception": 500,
        "error": 500,
        "warn": 400,
        "warning": 400,
        "info": 200,
        "debug": 100,
        "notset": 0,
    }

    return gcloud_severities.get(level, 0)


def holi_gcloud_serializer(event_dict, *args, **kwargs):
    # - Use Google fields for severity & other
    # - Add static applicationlevel fields (service & environment)

    event_dict["message"] = event_dict.pop("event")
    event_dict["severity"] = normalize_severity_from_loglevel(event_dict.pop("level"))
    event_dict["labels"] = LABELS
    return json.dumps(event_dict, *args, **kwargs)


class GraphQLLogFilter(logging.Filter):
    def filter(self, record):
        if record.msg and "GraphQLError" in record.msg:
            return None
        return True


LOGGING_CONFIG = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "json_formatter": {
            "()": structlog.stdlib.ProcessorFormatter,
            "processor": structlog.processors.JSONRenderer(serializer=holi_gcloud_serializer),
            "foreign_pre_chain": _shared_processors,
        },
        "console_formatter": {
            "()": structlog.stdlib.ProcessorFormatter,
            "processor": structlog.dev.ConsoleRenderer(),
            "foreign_pre_chain": _shared_processors,
        },
    },
    "handlers": {
        "json": {
            "class": "logging.StreamHandler",
            "formatter": "json_formatter",
        },
        "console": {
            "class": "logging.StreamHandler",
            "formatter": "console_formatter",
        },
    },
    # Prevent intentional graphql exceptions from displaying in log
    "filters": {
        "graphql_log_filter": {
            "()": GraphQLLogFilter,
        }
    },
    "loggers": {
        "graphql.execution.utils": {
            "level": "WARNING",
            "filters": ["graphql_log_filter"],
        },
        # "django.db.backends": {
        #     "level": "DEBUG",
        # },
    },
    "root": {
        "level": "INFO",
        "handlers": ["console" if sys.stdout.isatty() else "json"],
    },
}


def initialize_logging():
    logging.config.dictConfig(LOGGING_CONFIG)

    structlog.configure(
        processors=[
            *_shared_processors,
            structlog.stdlib.ProcessorFormatter.wrap_for_formatter,
        ],
        logger_factory=structlog.stdlib.LoggerFactory(),
        cache_logger_on_first_use=True,
    )

    return LOGGING_CONFIG
