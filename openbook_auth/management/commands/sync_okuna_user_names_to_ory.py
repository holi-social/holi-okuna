import http

import requests
from django.core.management.base import BaseCommand
from django.db.models import Q

from openbook.settings import ORY_BASE_URL
from openbook_auth.management.common import user_to_str, get_ory_error_str, ORY_HEADER
from openbook_auth.models import User


class Command(BaseCommand):
    help = "Sync Okuna users name on Ory"

    schema_id = None
    okuna_users = []
    users_patched = 0
    error_users_patched = 0

    def add_arguments(self, parser):
        parser.add_argument("--schema_id", type=str, required=False)

    def handle(self, *args, **options):
        self.schema_id = options["schema_id"]
        self._sync_okuna_users_info()
        print(f"Job completed. {self.users_patched} users patched ({self.error_users_patched} failed)")

    def _sync_okuna_users_info(self):
        print("Getting list of Okuna users with a name")

        for user in User.objects.filter(
            ~Q(username=""),
            (Q(profile__name__isnull=False) & ~Q(profile__name=""))
            | (Q(profile__last_name__isnull=False) & ~Q(profile__last_name="")),
        ).iterator():
            print(f"User: {user_to_str(user)}")
            self._patch_ory_user(user)

    def _patch_ory_user(self, user: User) -> None:
        print(f"Patching user {user_to_str(user)}")

        body_data = [
            {"op": "replace", "path": "/traits/given_name", "value": user.profile.name},
            {"op": "replace", "path": "/traits/family_name", "value": user.profile.last_name},
            {"op": "replace", "path": "/traits/name", "value": user.profile.full_name()},
        ]
        if self.schema_id:
            body_data.append(
                {
                    "op": "replace",
                    "path": "/schema_id",
                    "value": self.schema_id,
                }
            )

        response = requests.patch(
            f"{ORY_BASE_URL}/admin/identities/{user.username}", headers=ORY_HEADER, json=body_data
        )
        match response.status_code:
            case http.HTTPStatus.OK:
                self.users_patched += 1
                print(f"User {user_to_str(user)} patched")
            case http.HTTPStatus.NOT_FOUND:
                print(f"User {user_to_str(user)} not found in Ory")
            case _:
                response_data = response.json()
                print(
                    f"Error {response.status_code} while patching user {user_to_str(user)}: {get_ory_error_str(response_data)}"
                )
                self.error_users_patched += 1
