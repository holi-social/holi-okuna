import http
import requests
from django.core.management.base import BaseCommand

from openbook.settings import ORY_ACCESS_TOKEN, ORY_BASE_URL
from openbook_auth.management.commands.sync_okuna_user_names_to_ory import get_ory_error_str
from openbook_auth.management.common import for_every_ory_user, ory_user_to_str, ORY_HEADER


class Command(BaseCommand):
    help = "Update ory users schema"

    schema_id = ""
    total_users_updated = 0
    total_users_failed = 0

    def add_arguments(self, parser):
        parser.add_argument("schema_id", type=str)

    def handle(self, *args, **options):
        self.schema_id = options["schema_id"]
        for_every_ory_user(self._patch_ory_user)
        print(f"{self.total_users_updated} users updated")
        print(f"{self.total_users_failed} user updates failed")

    def _patch_ory_user(self, user: dict):
        if user["schema_id"] != self.schema_id:
            body_data = [
                {"op": "replace", "path": "/schema_id", "value": self.schema_id},
            ]
            print(f"Updating {ory_user_to_str(user)}")

            response = requests.patch(
                f"{ORY_BASE_URL}/admin/identities/{user['id']}", headers=ORY_HEADER, json=body_data
            )

            if response.status_code != http.HTTPStatus.OK:
                print(f"{get_ory_error_str(response.json())}, {ory_user_to_str(user)} update failed")
                self.total_users_failed += 1
            else:
                print(f"{ory_user_to_str(user)} updated")
                self.total_users_updated += 1
