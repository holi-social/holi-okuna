import uuid
from abc import abstractmethod


class CommentableNotificationContext:
    """
    represents an abstract domain model for comment holding entities
    and their dependent-on properties for sending comment-notifications
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
