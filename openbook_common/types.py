from enum import Enum

from strawberry_django_plus import gql


@gql.enum
class ReactionType(str, Enum):
    HEART = "HEART"
