import json
from typing import Any

import pytest

from openbook_auth.events import UserNameUpdatedEvent, UserPayload, UserDeletedEvent
from openbook_auth.models import User
from openbook_common.tests.helpers import make_user


# noinspection DuplicatedCode
def expected_user_payload(user: User) -> dict[str, Any]:
    return {
        "id": str(user.username),
        "name": user.profile.full_name(),
        "email": user.email,
        "identity": user.identity,
        "avatar": user.profile.avatar.url if user.profile.avatar else None,
        "aboutMe": user.profile.about_me,
        "location": user.profile.location,
    }


@pytest.mark.django_db
def test_should_create_user_name_updated_event():
    # GIVEN
    user = make_user()

    # WHEN
    event = UserNameUpdatedEvent(UserPayload.from_user(user))
    event_dict = event.to_dict()

    # THEN
    data = {"user": expected_user_payload(user)}
    encoded_data = json.dumps(data).encode("utf-8")
    expected_event_dict = {"eventType": "UserNameUpdated", "eventVersion": "1.1.0", "data": encoded_data}

    assert expected_event_dict == event_dict


@pytest.mark.django_db
def test_should_create_user_deleted_event():
    # GIVEN
    user = make_user()

    # WHEN
    event = UserDeletedEvent(UserPayload.from_user(user))
    event_dict = event.to_dict()

    # THEN
    data = {"user": expected_user_payload(user)}
    encoded_data = json.dumps(data).encode("utf-8")
    expected_event_dict = {"eventType": "UserDeleted", "eventVersion": "1.1.0", "data": encoded_data}

    assert expected_event_dict == event_dict
