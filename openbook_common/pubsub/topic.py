from enum import Enum

from openbook import settings


class Topic(Enum):
    OKUNA = f"okuna_{settings.ENVIRONMENT_ID}"
