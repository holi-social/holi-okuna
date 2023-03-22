import http
from datetime import timedelta

import requests
from dateutil import parser
from django.core.management.base import BaseCommand
from django.utils import timezone

from openbook.settings import ORY_ACCESS_TOKEN, ORY_BASE_URL
from openbook_auth.management.common import ory_user_to_str, get_ory_error_str, for_every_ory_user, user_to_str
from openbook_auth.models import User


class Command(BaseCommand):
    help = "Delete old e2e users on Ory and Okuna"

    base_url = f"{ORY_BASE_URL}/admin/identities/"
    headers = {"Authorization": f"Bearer {ORY_ACCESS_TOKEN}"}
    now = timezone.now()
    users_deleted_count = 0
    users_failed_count = 0

    def handle(self, *args, **options):
        for_every_ory_user(self._delete_ory_user)
        print(f"Job completed, {self.users_deleted_count} users deleted in Ory ({self.users_failed_count} failed)")
        self._delete_okuna_e2e_users()

    def _delete_ory_user(self, user: dict):
        creation_date = parser.isoparse(user["created_at"])
        email = user["traits"]["email"]
        if email.endswith("@e2etest.com") and creation_date <= self.now - timedelta(days=1):
            print(f"Deleting {ory_user_to_str(user)}")

            response = requests.delete(f"{self.base_url}{user['id']}", headers=self.headers)

            if response.status_code != http.HTTPStatus.NO_CONTENT:
                message = get_ory_error_str(response)
                print(f"{message}, Skipping {ory_user_to_str(user)} deletion")
                self.users_failed_count += 1
            else:
                print(f"{ory_user_to_str(user)} deleted in Ory")
                self.users_deleted_count += 1

    def _delete_okuna_e2e_users(self):
        print("\nDeleting Okuna users that ends with '@e2etest.com'")

        users_deleted_count = 0
        list_okuna_users = User.objects.filter(
            email__endswith="@e2etest.com", date_joined__lte=self.now - timedelta(days=1)
        )
        print(f"Found {len(list_okuna_users)} e2e users to delete in Okuna")

        for user in list_okuna_users:
            try:
                user.delete()
                users_deleted_count += 1
                print(f"User {user_to_str(user)} deleted in Okuna")
            except User.DoesNotExist:
                print(f"User {user_to_str(user)} doesn't exist in Okuna")
            except Exception as exc:
                print(f"Error deleting user {user_to_str(user)} in Okuna: {str(exc)}")

        print(f"Deleted {users_deleted_count}/{len(list_okuna_users)} users in Okuna")
