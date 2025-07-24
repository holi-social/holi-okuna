from enum import StrEnum
from typing import Self

from django.db.models import UUIDField, TextField, DateTimeField, ForeignKey, CASCADE
from django.utils.functional import classproperty

from openbook_auth.models import User
from openbook_common.models import ModelWithUUID


class Status(StrEnum):
    TO_DO = "TO_DO"
    CONTACTED = "CONTACTED"
    DOING = "DOING"
    WONT_DO = "WONT_DO"
    DONE = "DONE"

    @classproperty
    def choices(cls) -> list[tuple[str, str]]:  # noqa: N805
        return [(member.value, member.value) for member in cls]

    @classmethod
    def is_transition_allowed(cls, old_status: Self, new_status: Self) -> bool:
        _allowed_transitions: dict[Status, list[Status]] = {
            cls.TO_DO: [cls.CONTACTED, cls.WONT_DO],
            cls.CONTACTED: [cls.DOING, cls.WONT_DO],
            cls.DOING: [cls.DONE, cls.WONT_DO],
            cls.WONT_DO: [],
            cls.DONE: [],
        }

        return new_status in _allowed_transitions[old_status]


class VolunteeringOpportunityStatus(ModelWithUUID):
    external_volunteering_opportunity_id = UUIDField()
    user = ForeignKey(User, on_delete=CASCADE, null=False)
    status = TextField(choices=Status.choices)
    created_at = DateTimeField(auto_now_add=True, editable=False)
    updated_at = DateTimeField(auto_now=True, editable=False)
