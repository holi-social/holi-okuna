import os
from enum import Enum

ENVIRONMENT_ID = os.environ.get("ENVIRONMENT_ID", "development")


class Topic(Enum):
    OKUNA = f"okuna_{ENVIRONMENT_ID}"
