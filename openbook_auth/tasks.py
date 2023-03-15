import http

import requests
from django.conf import settings
from django_rq import job

from openbook_auth.errors import OryRequestError
from openbook_auth.models import User


@job("default")
def update_ory_user(user_id: int) -> None:
    user = User.objects.get(pk=user_id)

    headers = {"Authorization": f"Bearer {settings.ORY_ACCESS_TOKEN}"}
    data = [
            {
                "op": "replace",
                "path": "/schema_id",
                "value": settings.ORY_SCHEMA_ID
            }, {
                "op": "replace",
                "path": "/traits/given_name",
                "value": user.profile.name
            }, {
                "op": "replace",
                "path": "/traits/family_name",
                "value": user.profile.last_name
            }, {
                "op": "replace",
                "path": "/traits/name",
                "value": f"{user.profile.name} {user.profile.last_name}"
            },
    ]
    response = requests.patch(
        f"{settings.ORY_BASE_URL}/admin/identities/{user.username}", headers=headers, json=data
    )
    response_data = response.json()
    if response.status_code != http.HTTPStatus.OK:
        error = response_data.get("error")
        raise OryRequestError(
            message=f"Updating user {user.username} in ory failed: {error['message']}",
            error=error['message'],
            status_code=response.status_code
        )
