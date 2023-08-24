import http

import requests
import structlog
from django.conf import settings
from django_rq import job

from openbook_auth.errors import OryRequestError
from openbook_auth.models import User

logger = structlog.get_logger(__name__)


@job("default")
def update_ory_user_names(user_id: int) -> None:
    user = User.objects.get(pk=user_id)

    data = [
        {"op": "add", "path": "/traits/given_name", "value": user.profile.name},
        {"op": "add", "path": "/traits/family_name", "value": user.profile.last_name},
        {"op": "add", "path": "/traits/name", "value": f"{user.profile.full_name()}"},
    ]

    update_ory(user, data)


def update_ory_user_identity(user: User) -> bool:
    data = [
        {"op": "add", "path": "/traits/identity", "value": user.identity},
    ]
    try:
        update_ory(user, data)
        return True
    except OryRequestError as error:
        if error.status_code == 409:
            logger.error("Could not set identity for user %s. Identity already exists: %s", user.id, error.error)
        else:
            logger.error("Could not set identity for user %s. Ory response: %s", user.id, error.error)
    return False


def update_ory(user, data):
    headers = {"Authorization": f"Bearer {settings.ORY_ACCESS_TOKEN}"}
    response = requests.patch(f"{settings.ORY_BASE_URL}/admin/identities/{user.username}", headers=headers, json=data)
    response_data = response.json()
    if response.status_code != http.HTTPStatus.OK:
        error = response_data.get("error")
        raise OryRequestError(
            message=f"Updating user {user.username} in ory failed: {error['message']}",
            error=error["message"],
            status_code=response.status_code,
        )
