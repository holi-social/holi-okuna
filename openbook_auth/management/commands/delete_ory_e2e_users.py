import http
from datetime import timedelta

import requests
from dateutil import parser
from django.core.management.base import BaseCommand
from django.utils import timezone

from openbook.settings import ORY_ACCESS_TOKEN, ORY_BASE_URL
from openbook_auth.models import User


class Command(BaseCommand):
    help = "Delete old e2e users on Ory and Okuna"

    headers = {"Authorization": f"Bearer {ORY_ACCESS_TOKEN}"}
    base_url = f"{ORY_BASE_URL}/admin/identities/"
    now = timezone.now()

    def handle(self, *args, **options):
        list_ory_users = self._get_ory_e2e_users_list()
        if len(list_ory_users) > 0:
            self._delete_ory_matched_users(list_ory_users)
        else:
            print("No e2e users to delete found in Ory")
        self._delete_okuna_e2e_users()

    def _get_ory_e2e_users_list(self):
        print("Getting list of users that ends with \x1B[3m'@e2etest.com'\x1B[0m")
        list_ory_users = []
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

            else:
                for data in response_data:
                    creation_date = parser.isoparse(data["created_at"])
                    email = data["traits"]["email"]
                    if email.endswith("@e2etest.com") and creation_date <= self.now - timedelta(
                        days=1
                    ):
                        list_ory_users.append({"id": data["id"], "email": email})

                page += 1

        return list_ory_users

    def _delete_ory_matched_users(self, list_ory_users):
        users_deleted_count = 0

        for user in list_ory_users:
            print(f"Deleting user {user['email']}...")

            response = requests.delete(f"{self.base_url}{user['id']}", headers=self.headers)

            if response.status_code != http.HTTPStatus.NO_CONTENT:
                response_data = response.json()
                message = response_data["error"]["message"] if "error" in response_data else ""
                print(f"{message}, Skip user {user['email']} deletion")
            else:
                print(f"User {user['email']} deleted in Ory")
                users_deleted_count += 1

        print(
            f"Job completed, {users_deleted_count} users deleted ({len(list_ory_users) - users_deleted_count} failed)"
        )

    def _delete_okuna_e2e_users(self):
        print("\nDeleting Okuna users that ends with \x1B[3m'@e2etest.com'\x1B[0m")

        users_deleted_count = 0
        list_okuna_users = User.objects.filter(
            email__endswith="@e2etest.com", date_joined__lte=self.now - timedelta(days=1)
        )
        print(f"Found {len(list_okuna_users)} e2e users to delete in Okuna")

        for user in list_okuna_users:
            try:
                user.delete()
                users_deleted_count += 1
                print(f"User {user.email} deleted in Okuna")
            except User.DoesNotExist:
                print(f"User {user.email} doesn't exist in Okuna")
            except Exception as exc:
                print(f"Error deleting user {user.email} in Okuna: {str(exc)}")

        print(f"Deleted {users_deleted_count}/{len(list_okuna_users)} users in Okuna")
