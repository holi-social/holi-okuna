import json
from datetime import datetime
from unittest import mock

from django.test import TestCase
from django_rq import get_queue
from requests.models import Response
from rq.job import Job

from openbook import settings
from openbook_auth.models import User
from openbook_auth.tasks import update_ory_user
from openbook_common.tests.helpers import make_user


class TestUpdateOryUser(TestCase):
    user: User | None = None

    @classmethod
    def setUpTestData(cls) -> None:
        cls.user = make_user()

    @classmethod
    def tearDownClass(cls) -> None:
        cls.user.delete()
        super().tearDownClass()

    @mock.patch("requests.patch")
    def test_update_ory_user_success(self, mock_patch):
        json_body = [
            {"op": "add", "path": "/traits/given_name", "value": self.user.profile.name},
            {"op": "add", "path": "/traits/family_name", "value": self.user.profile.last_name},
            {
                "op": "add",
                "path": "/traits/name",
                "value": self.user.profile.full_name(),
            },
        ]
        response_content = json.dumps(
            {
                "created_at": "2019-08-24T14:15:22Z",
                "credentials": {},
                "id": self.user.username,
                "state": "active",
                "traits": {
                    "email": self.user.email,
                    "name": {"first": self.user.profile.name, "last": self.user.profile.last_name},
                },
                "updated_at": str(datetime.now()),
            }
        )
        response = Response()
        response.status_code = 200
        response._content = str.encode(response_content)
        mock_patch.return_value = response

        job: Job = update_ory_user.delay(self.user.id)

        mock_patch.assert_called_once_with(
            f"{settings.ORY_BASE_URL}/admin/identities/{self.user.username}",
            headers={"Authorization": f"Bearer {settings.ORY_ACCESS_TOKEN}"},
            json=json_body,
        )
        self.assertFalse(job.is_failed)
        self.assertTrue(job.is_finished)
        self.assertIsNone(job.result)

    @mock.patch("requests.patch")
    def test_update_ory_user_failure_user_not_exist(self, mock_patch):
        json_body = [
            {"op": "add", "path": "/traits/given_name", "value": self.user.profile.name},
            {"op": "add", "path": "/traits/family_name", "value": self.user.profile.last_name},
            {
                "op": "add",
                "path": "/traits/name",
                "value": self.user.profile.full_name(),
            },
        ]
        response_content = json.dumps(
            {"error": {"code": 404, "status": "Not Found", "message": "Unable to locate the resource"}}
        )
        response = Response()
        response.status_code = 404
        response._content = str.encode(response_content)
        mock_patch.return_value = response

        job: Job = update_ory_user.delay(self.user.id)

        mock_patch.assert_called_once_with(
            f"{settings.ORY_BASE_URL}/admin/identities/{self.user.username}",
            headers={"Authorization": f"Bearer {settings.ORY_ACCESS_TOKEN}"},
            json=json_body,
        )
        self.assertTrue(job.is_failed)
        self.assertFalse(job.is_finished)
        self.assertIsNone(job.result)

    @mock.patch("requests.patch")
    def test_update_ory_user_failure_bad_request(self, mock_patch):
        json_body = [
            {"op": "add", "path": "/traits/given_name", "value": self.user.profile.name},
            {"op": "add", "path": "/traits/family_name", "value": self.user.profile.last_name},
            {
                "op": "add",
                "path": "/traits/name",
                "value": self.user.profile.full_name(),
            },
        ]
        response_content = json.dumps({"error": {"code": 400, "status": "Bad request", "message": "Unsupported"}})
        response = Response()
        response.status_code = 400
        response._content = str.encode(response_content)
        mock_patch.return_value = response

        job: Job = update_ory_user.delay(self.user.id)

        mock_patch.assert_called_once_with(
            f"{settings.ORY_BASE_URL}/admin/identities/{self.user.username}",
            headers={"Authorization": f"Bearer {settings.ORY_ACCESS_TOKEN}"},
            json=json_body,
        )
        self.assertTrue(job.is_failed)
        self.assertFalse(job.is_finished)
        self.assertIsNone(job.result)
