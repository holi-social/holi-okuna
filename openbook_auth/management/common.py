# ruff: noqa: T201
from time import sleep
from typing import Callable

import requests
import http

from openbook import settings

ORY_HEADER = {"Authorization": f"Bearer {settings.ORY_ACCESS_TOKEN}"}


def for_every_ory_user(function: Callable[[dict], None]):
    """
    Expects a callback function that is called once for every user in Ory
    passing a dict with the data from the rest response from Ory.
    See: https://www.ory.sh/docs/reference/api#tag/identity/operation/listIdentities
    """
    per_page = 1000
    retry_count = 0
    next_page_url = None
    first = True
    while first or next_page_url:
        first = False
        if next_page_url:
            response = requests.get(next_page_url, headers=ORY_HEADER, timeout=30)
        else:
            params = {"per_page": per_page}
            response = requests.get(
                f"{settings.ORY_BASE_URL}/admin/identities/", params=params, headers=ORY_HEADER, timeout=30
            )

        if response.status_code != http.HTTPStatus.OK:
            message = get_ory_error_str(response)
            if retry_count < 3:
                print(f"Error getting users from Ory: {message} - Retry #{retry_count}")
                retry_count += 1
                sleep(2)
                continue
            print(f"Error getting users from Ory: {message} - Giving up")
            return

        else:
            # total = response.headers.get("x-total-count")  # noqa: ERA001
            retry_count = 0
            response_data = response.json()
            for user in response_data:
                function(user)
            next_page = response.links.get("next")
            if next_page:
                next_page_url = f"{settings.ORY_BASE_URL}/admin/identities/?{get_next_page_parameters(next_page)}"
            else:
                next_page_url = None


def get_next_page_parameters(next_page):
    return next_page.get("url").split("?")[1]


def get_ory_user(email):
    params = {"per_page": 1, "credentials_identifier": email}
    response = requests.get(
        f"{settings.ORY_BASE_URL}/admin/identities/", params=params, headers=ORY_HEADER, timeout=30
    )

    if no_ory_errors(response, "Error getting users from Ory"):
        response_json = response.json()
        if response_json:
            return response_json[0]
    return None


def no_ory_errors(response, msg="Error from Ory"):
    if response.status_code == http.HTTPStatus.OK:
        return True
    message = get_ory_error_str(response)
    print(f"{msg}: {message}")
    return False


def get_ory_error_str(response):
    response_data = response.json()
    error = response_data["error"] if "error" in response_data else []
    message = error["message"] if "message" in error else ""
    reason = f" ; reason: {error['reason']}" if "reason" in error else ""
    return f"{message}{reason}"


def user_to_str(user):
    return f"'{user.profile.full_name()}' (UUID: {user.username}, email: {user.email})"


def ory_user_to_str(user):
    return f"User '{user['id']}' - {user['traits']['email']}"
