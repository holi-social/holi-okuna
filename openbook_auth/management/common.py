from time import sleep
from typing import Callable, Any

import requests
import http

from openbook import settings

ORY_HEADER = {"Authorization": f"Bearer {settings.ORY_ACCESS_TOKEN}"}


def for_every_ory_user(function: Callable[[dict], None]):
    page = 1
    per_page = 2
    retry_count = 0
    while page == 1:  # or len(response_data) >= per_page:
        params = {"page": page, "per_page": per_page}
        response = requests.get(f"{settings.ORY_BASE_URL}/admin/identities/", params=params, headers=ORY_HEADER)

        if response.status_code != http.HTTPStatus.OK:
            message = get_ory_error_str(response_data)
            if retry_count < 3:
                print(f"Error getting users from Ory: {message} - Retry #{retry_count}")
                retry_count += 1
                sleep(2)
                continue
            print(f"Error getting users from Ory: {message} - Giving up")
            return

        else:
            retry_count = 0
            response_data = response.json()
            for user in response_data:
                function(user)
            page += 1


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
