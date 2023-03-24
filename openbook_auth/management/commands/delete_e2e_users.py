import http
from datetime import timedelta

import requests
from dateutil import parser
from django.core.management.base import BaseCommand
from django.utils import timezone

from openbook.settings import ORY_ACCESS_TOKEN, ORY_BASE_URL
from openbook_auth.management.common import (
    ory_user_to_str,
    get_ory_error_str,
    for_every_ory_user,
    user_to_str,
    get_ory_user,
)
from openbook_auth.models import User


class Command(BaseCommand):
    help = "Delete old e2e users on Ory and Okuna"

    base_url = f"{ORY_BASE_URL}/admin/identities/"
    headers = {"Authorization": f"Bearer {ORY_ACCESS_TOKEN}"}
    now = timezone.now()
    users_deleted_count = 0
    users_failed_count = 0
    email = None

    def add_arguments(self, parser):
        parser.add_argument("--ory", action="store_true", required=False)
        parser.add_argument("--okuna", action="store_true", required=False)
        parser.add_argument("--email", required=False)

    def handle(self, *args, **options):
        if not options["ory"] and not options["okuna"]:
            print("No option was specified. At least one of --ory and --okuna needs to be specified.")
            return
        self.email = options["email"]
        if options["ory"]:
            if self.email:
                user = get_ory_user(self.email)
                if user:
                    self._delete_ory_user(user)
            else:
                for_every_ory_user(self._delete_ory_user)
            print(f"Job completed, {self.users_deleted_count} users deleted in Ory ({self.users_failed_count} failed)")
        if options["okuna"]:
            self._delete_okuna_e2e_users()

    def _delete_ory_user(self, user: dict):
        creation_date = parser.isoparse(user["created_at"])
        email = user["traits"]["email"]
        if (self.email and self.email == email) or (
            email.endswith("@e2etest.com") and creation_date <= self.now - timedelta(days=1)
        ):
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
        print("\nDeleting Okuna users")

        if self.email:
            query = User.objects.filter(email=self.email)
        else:
            query = User.objects.filter(email__endswith="@e2etest.com", date_joined__lte=self.now - timedelta(days=1))
        print(f"{query.count()} e2e users to delete")
        (deleted_count, details) = query.delete()
        if "openbook_auth.User" in details:
            print(f"{details['openbook_auth.User']} e2e users deleted")
        print(f"{deleted_count} object delete in Okuna")
        print(f"Objects deleted: {details}")
