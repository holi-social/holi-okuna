import http
from collections import defaultdict

import requests
from django.core.management.base import BaseCommand

from openbook.settings import ORY_ACCESS_TOKEN, ORY_BASE_URL


class Command(BaseCommand):
    help = "Update ory users schema"

    headers = {"Authorization": f"Bearer {ORY_ACCESS_TOKEN}"}
    base_url = f"{ORY_BASE_URL}/admin/identities/"

    schema_id = ""
    list_users_by_schema = defaultdict(list)
    users_to_update_count = 0
    total_users_updated = 0
    body_data = {}

    def add_arguments(self, parser):
        parser.add_argument("schema_id", type=str)

    def handle(self, *args, **options):
        self.schema_id = str(options["schema_id"]).strip()
        if not self.schema_id:
            print("schema_id not valid, exit")
            return
        self.body_data = [
            {"op": "replace", "path": "/schema_id", "value": self.schema_id},
        ]
        self._get_ory_users_list()
        self._patch_ory_users_list()

    def _get_ory_users_list(self):
        print("Getting list of users with different schema")
        page = 1
        per_page = 500

        response_data = []
        while page == 1 or len(response_data) > 0:
            print(f"Downloading users info..{page * '.'}")

            params = {"page": page, "per_page": per_page}
            response = requests.get(self.base_url, params=params, headers=self.headers)
            response_data = response.json()

            if response.status_code != http.HTTPStatus.OK:
                message = response_data["error"]["message"] if "error" in response_data else ""
                print(f"{message}, Retry")
                continue

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
            print(f"Schema id: \x1B[3m'{schema_id}'\x1B[0m | Users:")
            for user in users:
                print(user["email"])

            self._patch_ory_matched_users(schema_id, users)

        print(f"Job completed, {self.total_users_updated} users updated")

    def _patch_ory_matched_users(self, schema_id, users):
        users_updated_count = 0
        choice = input(
            f"\nSchema \x1B[3m'{schema_id}'\x1B[0m has {len(users)} Ory users to update, enter (u) for update them, enter any other input to skip: "
        )
        if choice.lower() != "u":
            print("Skipped, 0 users updated")
            return

        for user in users:
            print(f"Updating user \x1B[3m'{user['email']}'\x1B[0m...")

            response = requests.patch(f"{self.base_url}{user['id']}", headers=self.headers, json=self.body_data)

            if response.status_code != http.HTTPStatus.OK:
                response_data = response.json()
                message = response_data["error"]["message"] if "error" in response_data else ""
                print(f"{message}, {user['email']} update skipped")
                continue

            print(f"{user['email']} updated")
            users_updated_count += 1

        self.total_users_updated += users_updated_count
        print(f"{users_updated_count} users updated")
