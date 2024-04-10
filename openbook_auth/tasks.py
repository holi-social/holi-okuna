import http
import threading
from datetime import datetime, timedelta

import pytz
import requests
import structlog
from django.conf import settings
from django_rq import job

from openbook.settings import CHAT_SERVER_NAME, CHAT_SERVER_URL
from openbook_auth.errors import OryRequestError
from openbook_auth.models import User
from dateutil import parser
from openbook.settings import ORY_SESSION_EXPIRY_IN_H
from openbook_common.utils.synchronized_set import SynchronizedSet

logger = structlog.get_logger(__name__)

ORY_HEADERS = {"Authorization": f"Bearer {settings.ORY_ACCESS_TOKEN}"}

session_ids = SynchronizedSet()

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
    response = requests.patch(f"{settings.ORY_BASE_URL}/admin/identities/{user_id}", headers=ORY_HEADERS, json=data, timeout=30)
    if response.status_code != http.HTTPStatus.OK:
        response_data = response.json()
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
    response = requests.put(url, headers=headers, json={}, timeout=30)
    return response.status_code == 201

def send_extend_ory_session(session_id:str):
    if not session_ids.add_if_absent(session_id): 
        return # we already sent an extension request that is still "in flight"
    try:
        response = requests.patch(f"{settings.ORY_BASE_URL}/admin/sessions/{session_id}/extend", headers=ORY_HEADERS, timeout=30)
        if response.status_code != http.HTTPStatus.OK:
            response_data = response.json()
            error = response_data.get("error")
            logger.warning("Extending the Ory session: %s failed with Error: %s", session_id, error['message'])
    except Exception as ex:
        logger.warning("Could not process Session Expiry. Exception: %s", repr(ex))
    finally:
        session_ids.remove(session_id)


def extend_ory_session(user_session:str, user_session_expiry:str):
    if user_session and user_session_expiry:
        try:
            if datetime.now(pytz.utc) > parser.parse(user_session_expiry) - timedelta(hours=ORY_SESSION_EXPIRY_IN_H):
                threading.Thread(target=send_extend_ory_session, args=(user_session,)).start()
        except Exception as ex:
            logger.warning("Could not process Session Expiry. Exception: %s", repr(ex))
