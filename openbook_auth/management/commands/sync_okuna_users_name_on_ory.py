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

    def handle(self, *args, **options):
        self._sync_okuna_users_list()

    def _sync_okuna_users_list(self):
        print("Getting list of Okuna users with first name and last name filled")

        for user in (
            User.objects.filter(profile__isnull=False)
            .exclude(
                Q(profile__name__isnull=True) | Q(profile__name__exact=""),
                Q(profile__last_name__isnull=True) | Q(profile__last_name__exact=""),
                Q(username__isnull=True) | Q(username__exact=""),
            )
            .iterator()
        ):
            if self._check_user_exists_in_ory(user):
                self._patching_ory_user(user)

    def _check_user_exists_in_ory(self, user: User) -> bool:
        name = user.profile.name
        last_name = user.profile.last_name
        print(f"Searching user: {name} {last_name} ({user.username}) in Ory")

        response = requests.get(f"{self.base_url}{user.username}", headers=self.headers)
        response_data = response.json()

        if response.status_code != http.HTTPStatus.OK:
            message = response_data["error"]["message"] if "error" in response_data else ""
            print(f"Error {response.status_code}: {message}")
            return False

        return True

    def _patching_ory_user(self, user: User) -> None:
        name = user.profile.name
        last_name = user.profile.last_name
        print(f"Patching user: {name} {last_name} ({user.username})")

        body_data = [
            {"op": "replace", "path": "/traits/given_name", "value": name},
            {"op": "replace", "path": "/traits/family_name", "value": last_name},
            {"op": "replace", "path": "/traits/name", "value": f"{name} {last_name}"},
        ]

        response = requests.patch(
            f"{settings.ORY_BASE_URL}/admin/identities/{user.username}", headers=self.headers, json=body_data
        )
        response_data = response.json()
        if response.status_code != http.HTTPStatus.OK:
            message = response_data["error"]["message"] if "error" in response_data else ""
            print(f"Error {response.status_code}: {message}")
            return

        print(f"User: {name} {last_name} ({user.username}) patched")
