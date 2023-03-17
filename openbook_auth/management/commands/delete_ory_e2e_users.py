import http

import requests
from django.core.management.base import BaseCommand

from openbook.settings import ORY_ACCESS_TOKEN, ORY_BASE_URL
from openbook_auth.models import User


class Command(BaseCommand):
    help = "Delete old e2e users on Ory"

    headers = {"Authorization": f"Bearer {ORY_ACCESS_TOKEN}"}
    base_url = f"{ORY_BASE_URL}/admin/identities/"
    list_users = []

    def handle(self, *args, **options):
        self._get_e2e_users_list()
        self._print_ory_users_list()
        self._delete_matched_users()

    def _get_e2e_users_list(self):
        print("Getting list of users that ends with \x1B[3m'@e2etest.com'\x1B[0m")
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
                if data["traits"]["email"].endswith("@e2etest.com"):
                    self.list_users.append({"id": data["id"], "email": data["traits"]["email"]})

            page += 1

    def _print_ory_users_list(self):
        choice = input(f"{len(self.list_users)} Ory users to delete found, enter (p) to print them: ")
        if choice.lower() == "p":
            for user in self.list_users:
                print(user["email"])

    def _delete_matched_users(self):
        users_deleted_count = 0
        choice = input(
            f"{len(self.list_users)} Ory users to delete, enter (d) to delete them, enter any other input to cancel: "
        )
        if choice.lower() != "d":
            print(f"Job canceled, {users_deleted_count} users deleted")
            return

        for user in self.list_users:
            print(f"Deleting user {user['email']}...")

            response = requests.delete(f"{self.base_url}{user['id']}", headers=self.headers)

            if response.status_code != http.HTTPStatus.NO_CONTENT:
                response_data = response.json()
                message = response_data["error"]["message"] if "error" in response_data else ""
                print(f"{message}, Skip user deletion")
                continue

            print(f"User {user['email']} deleted in Ory")
            users_deleted_count += 1
            self._delete_okuna_user(user["id"])

        print(f"Job completed, {users_deleted_count} users deleted")

    def _delete_okuna_user(self, username):
        try:
            User.objects.get(username=username).delete()
            print(f"User {username} deleted in Okuna")
        except User.DoesNotExist:
            print(f"User {username} doesn't exist in Okuna")
        except Exception:
            print(f"Error deleting user {username} in Okuna")
