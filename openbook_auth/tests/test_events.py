import json
from typing import Any

import pytest

from openbook_auth.events import UserNameUpdatedEvent, UserDeletedEvent, UserEmailUpdatedEvent, user_to_event_payload
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
def test_serialization_user_name_updated_event():
    # GIVEN
    user = make_user()

    # WHEN
    event = UserNameUpdatedEvent(user)

    # THEN
    expected_event_dict = {
        "eventType": "UserNameUpdated",
        "eventVersion": "1.1.0",
        "data": (json.dumps({"user": expected_user_payload(user)}).encode("utf-8")),
    }
    assert event.to_dict() == expected_event_dict


@pytest.mark.django_db
def test_serialization_user_email_updated_event():
    # GIVEN
    user = make_user()

    # WHEN
    event = UserEmailUpdatedEvent(user)

    # THEN
    expected_event_dict = {
        "eventType": "UserEmailUpdated",
        "eventVersion": "1.1.0",
        "data": (json.dumps({"user": expected_user_payload(user)}).encode("utf-8")),
    }
    assert event.to_dict() == expected_event_dict


@pytest.mark.django_db
def test_serialization_user_deleted_event():
    # GIVEN
    user = make_user()

    # WHEN
    event = UserDeletedEvent(user)

    # THEN
    expected_event_dict = {
        "eventType": "UserDeleted",
        "eventVersion": "1.1.0",
        "data": (json.dumps({"user": expected_user_payload(user)}).encode("utf-8")),
    }
    assert event.to_dict() == expected_event_dict


@pytest.mark.django_db
def test_user_payload():
    # GIVEN
    user = make_user()

    # WHEN
    payload = user_to_event_payload(user)

    # THEN
    expected_payload = expected_user_payload(user)
    assert payload == expected_payload


@pytest.mark.django_db
def test_user_payload_without_profile():
    # GIVEN
    user = make_user()
    user.profile = None

    # WHEN
    payload = user_to_event_payload(user)

    # THEN
    expected_payload = {
        "id": str(user.username),
        "name": None,
        "email": user.email,
        "identity": user.identity,
        "avatar": None,
        "aboutMe": None,
        "location": None,
    }
    assert payload == expected_payload
