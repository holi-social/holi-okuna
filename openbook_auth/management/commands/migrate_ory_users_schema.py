import http
from collections import defaultdict
from time import sleep

import requests
from django.core.management.base import BaseCommand

from openbook.settings import ORY_ACCESS_TOKEN, ORY_BASE_URL
from openbook_auth.management.commands.sync_okuna_user_names_to_ory import get_ory_error_str


class Command(BaseCommand):
    help = "Update ory users schema"

    headers = {"Authorization": f"Bearer {ORY_ACCESS_TOKEN}"}
    base_url = f"{ORY_BASE_URL}/admin/identities/"

    schema_id = ""
    list_users_by_schema = defaultdict(list)
    users_to_update_count = 0
    total_users_updated = 0

    def add_arguments(self, parser):
        parser.add_argument("schema_id", type=str)

    def handle(self, *args, **options):
        self.schema_id = str(options["schema_id"])
        self._get_ory_users_list()
        self._patch_ory_users_list()

    def _get_ory_users_list(self):
        print("Getting list of users with different schema")
        page = 1
        per_page = 1000
        retry_count = 0

        response_data = []
        while page == 1 or len(response_data) >= per_page:
            print(f"Downloading users info {page * '.'}")

            params = {"page": page, "per_page": per_page}
            response = requests.get(self.base_url, params=params, headers=self.headers)
            response_data = response.json()

            if response.status_code != http.HTTPStatus.OK:
                message = get_ory_error_str(response_data)
                if retry_count < 3:
                    print(f"{message}, Retry #{retry_count}")
                    retry_count += 1
                    sleep(2)
                    continue
                print(f"{message}, Giving up")
                return

            retry_count = 0
            for data in response_data:
                if data["schema_id"] != self.schema_id:
                    self.list_users_by_schema[data["schema_id"]].append(
                        {"id": data["id"], "email": data["traits"]["email"]}
                    )
                    self.users_to_update_count += 1

            page += 1

    def _patch_ory_users_list(self):
        choice = input(
            f"{self.users_to_update_count} Ory users to patch found, enter (p) to print them, enter any other input to cancel: "
        )
        if choice.lower() != "p":
            print("Job canceled")
            return

        for schema_id, users in self.list_users_by_schema.items():
            print("\n-------------------------------------------------------")
            print(f"Schema id: '{schema_id}' \nUsers:")
            for user in users:
                print(user["email"])

            self._patch_ory_matched_users(schema_id, users)

        print(f"Job completed, {self.total_users_updated} users updated")

    def _patch_ory_matched_users(self, schema_id, users):
        users_updated_count = 0
        choice = input(
            f"\nSchema '{schema_id}' has {len(users)} Ory users to update, enter (u) for update them, enter any other input to skip: "
        )
        if choice.lower() != "u":
            print("Skipped, 0 users updated")
            return

        body_data = [
            {"op": "replace", "path": "/schema_id", "value": self.schema_id},
        ]
        for user in users:
            print(f"Updating user '{user['email']}'")

            response = requests.patch(f"{self.base_url}{user['id']}", headers=self.headers, json=body_data)

            if response.status_code != http.HTTPStatus.OK:
                message = get_ory_error_str(response.json())
                print(f"{message}, {user['email']} update skipped")
                continue

            print(f"{user['email']} updated")
            users_updated_count += 1

        self.total_users_updated += users_updated_count
        print(f"{users_updated_count} users updated")
