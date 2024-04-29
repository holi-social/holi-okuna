import uuid
from abc import abstractmethod
from enum import Enum
import strawberry
from django.db.models import Model


class Commentable(Model):
    """
    represents an abstract domain model for comment parents
    """

    class Meta:
        abstract = True

    @property
    @abstractmethod
    def id(self) -> uuid.UUID:
        raise NotImplementedError

    @property
    @abstractmethod
    def text(self) -> str:
        raise NotImplementedError

    @property
    @abstractmethod
    def title(self) -> str:
        raise NotImplementedError

    @property
    @abstractmethod
    def context(self) -> str:
        raise NotImplementedError

    @property
    @abstractmethod
    def is_public(self) -> bool:
        raise NotImplementedError


@strawberry.enum
class CommentableType(Enum):
    POST = "post"
    DISCUSSION = "discussion"
