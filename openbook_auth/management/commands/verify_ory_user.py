# ruff: noqa: T201
from django.core.management import BaseCommand
import requests
from openbook.settings import ORY_BASE_URL
from openbook_auth.management.common import (
    get_ory_error_str,
    ORY_HEADER,
    ory_user_to_str,
    get_ory_user,
)
import http


class Command(BaseCommand):
    email = None

    def add_arguments(self, parser):
        parser.add_argument("email")

    def handle(self, *args, **options):
        self.email = options["email"]
        user = get_ory_user(self.email)
        if user:
            body_data = [
                {"op": "replace", "path": "/verifiable_addresses/0/verified", "value": True},
                {"op": "replace", "path": "/verifiable_addresses/0/status", "value": "completed"},
            ]
            response = requests.patch(
                f"{ORY_BASE_URL}/admin/identities/{user['id']}", headers=ORY_HEADER, json=body_data, timeout=30
            )
            if response.status_code != http.HTTPStatus.OK:
                print(get_ory_error_str(response))
            else:
                print("User is verified: " + ory_user_to_str(user))
