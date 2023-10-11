from django.core.management import BaseCommand
import requests
from openbook.settings import ORY_BASE_URL
from openbook_auth.management.common import (
    ORY_HEADER,
    no_ory_errors,
)

from openbook_auth.tasks import update_ory


class Command(BaseCommand):
    help = "Can be used to set an Ory user to verified and/or set a new password or a new identity for a user"

    def add_arguments(self, parser):
        parser.add_argument("ory_user_id")
        parser.add_argument("--password", required=False)
        parser.add_argument("--identity", required=False)
        parser.add_argument("--verified", action="store_true", required=False)

    def handle(self, *args, **options):
        ory_user_id = options["ory_user_id"]
        if options["verified"]:
            self.set_verified(ory_user_id)
        if options["password"]:
            self.set_password(ory_user_id, options["password"])
        if options["identity"]:
            self.set_identity(ory_user_id, options["identity"])

    def set_verified(self, ory_id):
        body_data = [
            {"op": "replace", "path": "/verifiable_addresses/0/verified", "value": True},
            {"op": "replace", "path": "/verifiable_addresses/0/status", "value": "completed"},
        ]
        update_ory(ory_id, body_data)
        print(f"User {ory_id} set to verified")

    def set_password(self, ory_id, new_password):
        resp = requests.get(f"{ORY_BASE_URL}/admin/identities/{ory_id}", headers=ORY_HEADER)
        ory_user = resp.json()
        ory_user["credentials"]["password"]["config"] = {"password": new_password}
        response = requests.put(f"{ORY_BASE_URL}/admin/identities/{ory_id}", headers=ORY_HEADER, json=ory_user)
        if no_ory_errors(response):
            print(f"User {ory_id} password set to {new_password}")

    def set_identity(self, ory_id, identity):
        body_data = [
            {"op": "add", "path": "/traits/identity", "value": identity},
        ]
        update_ory(ory_id, body_data)
        print(f"User {ory_id} identity set")
