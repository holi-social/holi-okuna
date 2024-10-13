# ruff: noqa: T201
import http
import requests
from django.core.management.base import BaseCommand

from openbook.settings import ORY_BASE_URL
from openbook_auth.management.commands.sync_okuna_user_names_to_ory import get_ory_error_str
from openbook_auth.management.common import for_every_ory_user, ory_user_to_str, ORY_HEADER


class Command(BaseCommand):
    help = "Move identities from traits to metadata_public"

    total_users_updated = 0
    total_users_failed = 0
    no_update_needed = 0

    def handle(self, *args, **options):
        # self._patch_ory_user({"id": "869e0ade-1561-4cf8-81dc-ca7552367325", "traits": {"identity": "ho5", "email": "test@sxx"}})  # noqa: ERA001
        for_every_ory_user(self._patch_ory_user)
        print(f"{self.total_users_updated} users updated")
        print(f"{self.total_users_failed} user updates failed")
        print(f"{self.no_update_needed} users not updated")

    def _patch_ory_user(self, user: dict):
        if "identity" in user["traits"]:
            count = self.total_users_updated + self.total_users_failed + 1
            body_data = [
                {"op": "add", "path": "/metadata_public/identity", "value": user["traits"]["identity"]},
            ]
            print(f"{count} Updating {ory_user_to_str(user)}")

            response = requests.patch(
                f"{ORY_BASE_URL}/admin/identities/{user['id']}", headers=ORY_HEADER, json=body_data, timeout=30
            )

            if response.status_code != http.HTTPStatus.OK:
                print(f"{count} {get_ory_error_str(response)}, {ory_user_to_str(user)} setting identity failed")
                self.total_users_failed += 1
            else:
                body_data = [
                    {"op": "remove", "path": "/traits/identity"},
                ]
                response = requests.patch(
                    f"{ORY_BASE_URL}/admin/identities/{user['id']}", headers=ORY_HEADER, json=body_data, timeout=30
                )
                if response.status_code != http.HTTPStatus.OK:
                    print(f"{count} {get_ory_error_str(response)}, {ory_user_to_str(user)} removing identity failed")
                    self.total_users_failed += 1
                else:
                    print(f"{count} {ory_user_to_str(user)} updated")
                    self.total_users_updated += 1
        else:
            self.no_update_needed += 1
