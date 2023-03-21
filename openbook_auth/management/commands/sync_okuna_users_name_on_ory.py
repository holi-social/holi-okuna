import http

import requests
from django.conf import settings
from django.core.management.base import BaseCommand
from django.db.models import Q

from openbook.settings import ORY_ACCESS_TOKEN, ORY_BASE_URL
from openbook_auth.models import User


class Command(BaseCommand):
    help = "Sync Okuna users name on Ory"

    headers = {"Authorization": f"Bearer {ORY_ACCESS_TOKEN}"}
    base_url = f"{ORY_BASE_URL}/admin/identities/"
    okuna_users = []
    users_patched = 0
    error_users_patched = 0

    def handle(self, *args, **options):
        self._sync_okuna_users_info()
        print(f"Job completed. {self.users_patched} users patched ({self.error_users_patched} failed)")

    def _sync_okuna_users_info(self):
        print("Getting list of Okuna users with first name and last name filled")

        for user in (
            User.objects.exclude(profile__isnull=True)
            .exclude(
                Q(profile__name__isnull=True) | Q(profile__name__exact=""),
                Q(profile__last_name__isnull=True) | Q(profile__last_name__exact=""),
                Q(username__isnull=True) | Q(username__exact=""),
            )
            .iterator()
        ):
            if self._check_user_exists_in_ory(user):
                self._patch_ory_user(user)
            else:
                name = user.profile.name
                last_name = user.profile.last_name
                print(f"User {name} {last_name} ({user.email}) doesn't exist")

    def _check_user_exists_in_ory(self, user: User) -> bool:
        full_name = user.profile.full_name
        print(f"Searching user: {full_name} ({user.email}) in Ory")

        response = requests.get(f"{self.base_url}{user.username}", headers=self.headers)
        response_data = response.json()

        if response.status_code != http.HTTPStatus.OK:
            message = response_data["error"]["message"] if "error" in response_data else ""
            print(f"Error {response.status_code} while checking user {full_name} ({user.email}): {message}")
            if response.status_code != http.HTTPStatus.NOT_FOUND:
                self.error_users_patched += 1
            return False

        return True

    def _patch_ory_user(self, user: User) -> None:
        name = user.profile.name
        last_name = user.profile.last_name
        full_name = user.profile.full_name
        print(f"Patching user: {full_name} ({user.email})")

        body_data = [
            {"op": "replace", "path": "/traits/given_name", "value": name},
            {"op": "replace", "path": "/traits/family_name", "value": last_name},
            {"op": "replace", "path": "/traits/name", "value": f"{full_name}"},
        ]

        response = requests.patch(
            f"{settings.ORY_BASE_URL}/admin/identities/{user.username}", headers=self.headers, json=body_data
        )
        response_data = response.json()
        if response.status_code != http.HTTPStatus.OK:
            message = response_data["error"]["message"] if "error" in response_data else ""
            print(f"Error {response.status_code} while patching user {full_name} ({user.email}): {message}")
            self.error_users_patched += 1
            return

        self.users_patched += 1
        print(f"User: {full_name} ({user.email}) patched")
