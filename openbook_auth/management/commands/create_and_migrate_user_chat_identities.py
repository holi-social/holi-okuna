import http
import random

import requests
from django.core.management.base import BaseCommand
from django.db.models import Q

from openbook.settings import ORY_BASE_URL
from openbook_auth.management.common import user_to_str, get_ory_error_str, ORY_HEADER
from openbook_auth.models import User


class Command(BaseCommand):
    help = "Create chat identities for users and migrate them to Ory"

    users_patched = 0
    error_users_patched = 0

    def handle(self, *args, **options):
        self._update_chat_identities()
        print(f"Job completed. {self.users_patched} users patched ({self.error_users_patched} failed)")

    def _update_ory_user_identity_and_save_in_okuna(self, user: User, identity: str) -> int:
        print(f"Updating Ory user {user_to_str(user)} with identity {identity}")
        body_data = [
            {"op": "add", "path": "/traits/identity", "value": identity},
        ]
        response = requests.patch(
            f"{ORY_BASE_URL}/admin/identities/{user.username}", headers=ORY_HEADER, json=body_data
        )
        match response.status_code:
            case http.HTTPStatus.OK:
                self.users_patched += 1
                user.save(identity=identity)
                print(f"User {user_to_str(user)} patched")
            case http.HTTPStatus.NOT_FOUND:
                print(f"User {user_to_str(user)} not found in Ory")
            case http.HTTPStatus.CONFLICT:
                print(f"A user with identity {identity} already exists.")
            case _:
                print(
                    f"Error {response.status_code} while patching user {user_to_str(user)}: {get_ory_error_str(response)}"
                )
                self.error_users_patched += 1

        return response.status_code

    def _create_and_store_unique_user_chat_identity(self, user: User) -> None:
        base_identity = user.profile.name
        if user.profile.last_name:
            base_identity += f"{user.profile.last_name}"

        print(f"Generating an unique identity for user {user_to_str(user)}")
        identity = User.unique_identity(base_identity.strip().lower())

        while self._update_ory_user_identity_and_save_in_okuna(user, identity) == http.HTTPStatus.CONFLICT:
            identity = f"{base_identity}{random.randint(1, 100)}"

    def _update_chat_identities(self) -> None:
        print("Getting list of Okuna users without an identity and with a name")

        for user in (
            User.objects.exclude(Q(profile__name__isnull=True) | Q(profile__name=""))
            .filter(Q(identity__isnull=True) | Q(identity=""))
            .iterator()
        ):
            print(f"User: {user_to_str(user)}")
            self._create_and_store_unique_user_chat_identity(user)
