from enum import Enum

import strawberry


@strawberry.enum
class VisibilityFilter(Enum):
    MEMBERS = "MEMBERS"
    PUBLIC = "PUBLIC"
    ALL = "ALL"
