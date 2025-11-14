from enum import StrEnum
from typing import Self

from django.db.models import TextField, DateTimeField, ForeignKey, CASCADE, Index
from django.utils.functional import classproperty

from openbook_auth.models import User
from openbook_common.models import ModelWithUUID


class Status(StrEnum):
    PLANNED = "PLANNED"
    SIGNED = "SIGNED"

    @classproperty
    def choices(cls) -> list[tuple[str, str]]:  # noqa: N805
        return [(member.value, member.value) for member in cls]

    @classmethod
    def is_transition_allowed(cls, old_status: Self, new_status: Self) -> bool:
        _allowed_transitions: dict[Status, list[Status]] = {
            cls.PLANNED: [cls.SIGNED],
            cls.SIGNED: [],
        }

        return new_status in _allowed_transitions[old_status]


class PetitionStatus(ModelWithUUID):
    external_petition_id = TextField(max_length=255, null=False, blank=False)
    user = ForeignKey(User, on_delete=CASCADE, null=False)
    status = TextField(choices=Status.choices)
    created_at = DateTimeField(auto_now_add=True, editable=False)
    updated_at = DateTimeField(auto_now=True, editable=False)

    class Meta:
        indexes = [
            Index(fields=["user"]),
            Index(fields=["external_petition_id"]),
        ]
