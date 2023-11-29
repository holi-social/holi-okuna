import http

import requests
import structlog
from django.conf import settings
from django_rq import job

from openbook.settings import CHAT_SERVER_NAME, CHAT_SERVER_URL
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

    update_ory(user.username, data)


def update_ory_user_identity(user: User) -> bool:
    data = [
        {"op": "add", "path": "/metadata_public/identity", "value": user.identity},
    ]
    try:
        update_ory(user.username, data)
        return True
    except OryRequestError as error:
        if error.status_code == 409:
            logger.warning("Could not set identity for user %s. Identity already exists: %s", user.id, error.error)
        else:
            logger.warning("Could not set identity for user %s. Ory response: %s", user.id, error.error)
    return False


def update_ory(user_id, data):
    if settings.ORY_ACCESS_TOKEN == "unknown":  # default in templates/.env
        logger.error("ory access token is unknown, can't update ory. Will skip call to ory API!")
        return
    headers = {"Authorization": f"Bearer {settings.ORY_ACCESS_TOKEN}"}
    response = requests.patch(f"{settings.ORY_BASE_URL}/admin/identities/{user_id}", headers=headers, json=data)
    response_data = response.json()
    if response.status_code != http.HTTPStatus.OK:
        error = response_data.get("error")
        raise OryRequestError(
            message=f"Updating user {user_id} in ory failed: {error['message']}",
            error=error["message"],
            status_code=response.status_code,
        )


def create_matrix_user_account(identity: str):
    """try to create a matrix account with the provided identity. Returns True, when the call created a new account, False otherwise"""
    url = f"{CHAT_SERVER_URL}/_synapse/admin/v2/users/%40{identity}%3A{CHAT_SERVER_NAME}"
    headers = {"Authorization": f"Bearer {settings.CHAT_ADMIN_ACCESS_TOKEN}"}
    response = requests.put(url, headers=headers, json={})
    return response.status_code == 201
