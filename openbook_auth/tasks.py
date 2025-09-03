import http
import threading
from datetime import datetime, timedelta

import pytz
import requests
import structlog
from dateutil import parser
from django.conf import settings
from django_rq import job
from requests import RequestException
from rest_framework.exceptions import ValidationError

from openbook.settings import CHAT_SERVER_NAME, CHAT_SERVER_URL
from openbook.settings import ORY_SESSION_EXPIRY_IN_H
from openbook_auth.errors import OryRequestError, MatrixRequestError
from openbook_auth.models import User, AccountType
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
    # TODO: handle requests.exceptions.Timeout
    response = requests.patch(
        f"{settings.ORY_BASE_URL}/admin/identities/{user_id}", headers=ORY_HEADERS, json=data, timeout=30
    )
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
    try:
        response = requests.put(url, headers=headers, json={}, timeout=30)
        if response.status_code >= 400:
            response_data = response.json()
            error = response_data.get("error")
            raise MatrixRequestError("Error creating user account in Matrix Server", error, response.status_code)
        # status_code is 200, when the user already exists and 201, when it was created
        return response.status_code == 201
    except RequestException as ex:
        raise MatrixRequestError("Could not send request to the Matrix Server", str(ex), 0) from None


def send_extend_ory_session(session_id: str):
    if not session_ids.add_if_absent(session_id):
        return  # we already sent an extension request that is still "in flight"
    try:
        response = requests.patch(
            f"{settings.ORY_BASE_URL}/admin/sessions/{session_id}/extend", headers=ORY_HEADERS, timeout=30
        )
        if response.status_code != http.HTTPStatus.OK:
            response_data = response.json()
            error = response_data.get("error")
            logger.error("Extending the Ory session: %s failed with Error: %s", session_id, error["message"])
    except Exception as ex:
        logger.error("Could not process Session Expiry. Exception: %s", repr(ex))
    finally:
        session_ids.remove(session_id)


def get_account_type(user_id: str):
    response = requests.get(f"{settings.ORY_BASE_URL}/admin/identities/{user_id}", headers=ORY_HEADERS, timeout=30)
    if response.status_code != http.HTTPStatus.OK:
        response_data = response.json()
        error = response_data.get("error")
        logger.error("Getting Ory User: %s failed with Error: %s", user_id, error["message"])
        raise error
    else:
        json = response.json()
        credentials = json.get("credentials", {})
        oidc = credentials.get("oidc")
        if oidc:
            if any(v.startswith("google") for v in oidc.get("identifiers", [])):
                return AccountType.GOOGLE
            if any(v.startswith("apple") for v in oidc.get("identifiers", [])):
                return AccountType.APPLE
            if any(v.startswith("facebook") for v in oidc.get("identifiers", [])):
                return AccountType.FACEBOOK
            return AccountType.UNKNOWN
        if credentials.get("password"):
            return AccountType.EMAIL
        return AccountType.OTP


def extend_ory_session(user_session: str, user_session_expiry: str):
    if user_session and user_session_expiry:
        try:
            if datetime.now(pytz.utc) > parser.parse(user_session_expiry) - timedelta(hours=ORY_SESSION_EXPIRY_IN_H):
                threading.Thread(target=send_extend_ory_session, args=(user_session,)).start()
        except Exception as ex:
            logger.warning("Could not process Session Expiry. Exception: %s", repr(ex))


def generate_identity_when_needed(current_user):
    if not current_user.identity and current_user.profile.full_name():
        identity_wish = User.sanitize_identity_input(current_user.profile.full_name())
        current_identity_trial = identity_wish
        counter = 0
        taken_identities = []

        if User.is_identity_taken(current_identity_trial):
            taken_identities = User.get_taken_identities(identity_wish)
            current_identity_trial, counter = User.next_unique_identity(identity_wish, taken_identities, counter)

        while True:
            # find an available matrix identity
            while not create_matrix_user_account(current_identity_trial):
                current_identity_trial, counter = User.next_unique_identity(identity_wish, taken_identities, counter)
            # store the created matrix identity
            try:
                current_user.identity = current_identity_trial
                current_user.save()
            except ValidationError as error:
                # somehow we have a collision in Okuna, so we keep trying new identities
                if "A user with that identity already exists." in error.message_dict["identity"]:
                    taken_identities = User.get_taken_identities(identity_wish)
                    current_identity_trial, counter = User.next_unique_identity(
                        identity_wish, taken_identities, counter
                    )
                    continue
                else:
                    raise error
            break

        tries = 0
        while tries < 3:
            if update_ory_user_identity(current_user):
                break  # Ory update was successful, and there was no collision. We are done.
            tries += 1
        if tries >= 3:
            logger.error(
                "MANUAL INTERVENTION NEEDED!!! Could not write identity to Ory. Ory user id: %s - identity: '%s'. Maybe Ory was not reachable? Use the patch_ory admin command to set it manually.",
                current_user.username,
                current_user.identity,
            )
