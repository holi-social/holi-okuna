import abc
import uuid
from dataclasses import dataclass
from django.db import models


@dataclass(frozen=True)
class CommentNotificationContext:
    id: uuid.UUID
    title: str
    context: str | None
    is_public: bool = False

    def to_dict(self):
        return {
            "id": str(self.id),
            "title": self.title,
            "context": self.context,
            "isPublic": self.is_public,
        }


class CommentNotificationMixin(
    models.Model, metaclass=type("CommentNotificationMixinMeta", (abc.ABCMeta, type(models.Model)), {})
):
    class Meta:
        abstract = True

    @property
    @abc.abstractmethod
    def comment_notification_context(self) -> CommentNotificationContext:
        raise NotImplementedError()
