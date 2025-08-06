import json
import time
from datetime import datetime, timedelta
from unittest import mock

import pytz
from django.test import TestCase
from requests.models import Response
from requests.exceptions import HTTPError
from rq.job import Job

from openbook import settings
from openbook.settings import ORY_SESSION_EXPIRY_IN_H
from openbook_auth.models import User, AccountType
from openbook_auth.tasks import update_ory_user_names, extend_ory_session, get_account_type
from openbook_common.tests.helpers import make_user
from openbook_common.utils.count_down_latch import CountDownLatch
from openbook_common.utils.test import MockJsonResponse


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

        job: Job = update_ory_user_names.delay(self.user.id)

        mock_patch.assert_called_once_with(
            f"{settings.ORY_BASE_URL}/admin/identities/{self.user.username}",
            headers={"Authorization": f"Bearer {settings.ORY_ACCESS_TOKEN}"},
            json=json_body,
            timeout=30,
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

        job: Job = update_ory_user_names.delay(self.user.id)

        mock_patch.assert_called_once_with(
            f"{settings.ORY_BASE_URL}/admin/identities/{self.user.username}",
            headers={"Authorization": f"Bearer {settings.ORY_ACCESS_TOKEN}"},
            json=json_body,
            timeout=30,
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

        job: Job = update_ory_user_names.delay(self.user.id)

        mock_patch.assert_called_once_with(
            f"{settings.ORY_BASE_URL}/admin/identities/{self.user.username}",
            headers={"Authorization": f"Bearer {settings.ORY_ACCESS_TOKEN}"},
            json=json_body,
            timeout=30,
        )
        self.assertTrue(job.is_failed)
        self.assertFalse(job.is_finished)
        self.assertIsNone(job.return_value())

    @mock.patch("requests.patch")
    def test_extend_ory_session_success(self, mock_patch):
        cdl = self.configure_mock_with_delayed_response(mock_patch)

        session = "some_session"
        expiry = (datetime.now(pytz.utc) + timedelta(hours=(ORY_SESSION_EXPIRY_IN_H - 24))).isoformat()
        extend_ory_session(session, expiry)
        cdl.count_down()
        mock_patch.assert_called_once_with(
            f"{settings.ORY_BASE_URL}/admin/sessions/{session}/extend",
            headers={"Authorization": f"Bearer {settings.ORY_ACCESS_TOKEN}"},
            timeout=30,
        )

    @mock.patch("requests.patch")
    def test_extend_ory_session_success_batched(self, mock_patch):
        cdl = self.configure_mock_with_delayed_response(mock_patch)

        session = "some_session"
        expiry = (datetime.now(pytz.utc) + timedelta(hours=(ORY_SESSION_EXPIRY_IN_H - 24))).isoformat()
        extend_ory_session(session, expiry)
        extend_ory_session(session, expiry)
        extend_ory_session(session, expiry)
        cdl.count_down()
        mock_patch.assert_called_once_with(
            f"{settings.ORY_BASE_URL}/admin/sessions/{session}/extend",
            headers={"Authorization": f"Bearer {settings.ORY_ACCESS_TOKEN}"},
            timeout=30,
        )

    @mock.patch("requests.patch")
    def test_extend_ory_session_success_second_round_called_again(self, mock_patch):
        cdl = self.configure_mock_with_delayed_response(mock_patch)

        session = "some_session"
        expiry = (datetime.now(pytz.utc) + timedelta(hours=(ORY_SESSION_EXPIRY_IN_H - 24))).isoformat()
        extend_ory_session(session, expiry)
        extend_ory_session(session, expiry)
        extend_ory_session(session, expiry)
        cdl.count_down()
        mock_patch.assert_called_once_with(
            f"{settings.ORY_BASE_URL}/admin/sessions/{session}/extend",
            headers={"Authorization": f"Bearer {settings.ORY_ACCESS_TOKEN}"},
            timeout=30,
        )

        time.sleep(0.01)  # wait for ory session thread to finish
        mock_patch.reset_mock()
        cdl = self.configure_mock_with_delayed_response(mock_patch)
        extend_ory_session(session, expiry)
        cdl.count_down()
        mock_patch.assert_called_once_with(
            f"{settings.ORY_BASE_URL}/admin/sessions/{session}/extend",
            headers={"Authorization": f"Bearer {settings.ORY_ACCESS_TOKEN}"},
            timeout=30,
        )

    def configure_mock_with_delayed_response(self, mock_patch, status_code=200, content=None):
        if content is None:
            content = {}
        cdl = CountDownLatch(1)
        response = Response()
        response.status_code = status_code
        response._content = str.encode(json.dumps(content))

        def delayed_response(*args, **kwargs):
            cdl.wait_for()
            return response

        mock_patch.side_effect = delayed_response
        return cdl

    @mock.patch("requests.patch")
    def test_extend_ory_session_not_needed(self, mock_patch):
        session = "some_session"
        expiry = (datetime.now(pytz.utc) + timedelta(hours=(ORY_SESSION_EXPIRY_IN_H + 24))).isoformat()
        extend_ory_session(session, expiry)
        mock_patch.assert_not_called()

    @mock.patch("requests.get")
    def test_get_account_type_fetches_ory_identity(self, mock_get):
        mock_get.return_value = MockJsonResponse({})
        user_id = "some_id"

        get_account_type("some_id")

        mock_get.assert_called_once_with(
            f"{settings.ORY_BASE_URL}/admin/identities/{user_id}",
            headers={"Authorization": f"Bearer {settings.ORY_ACCESS_TOKEN}"},
            timeout=30,
        )

    @mock.patch("requests.get")
    def test_get_account_type_should_return_provider_for_google_account(self, mock_get):
        mock_get.return_value = MockJsonResponse({"credentials": {"oidc": {"identifiers": ["google-123"]}}})

        result = get_account_type("some_id")

        self.assertEqual(result, AccountType.GOOGLE)

    @mock.patch("requests.get")
    def test_get_account_type_should_return_provider_for_apple_account(self, mock_get):
        mock_get.return_value = MockJsonResponse({"credentials": {"oidc": {"identifiers": ["apple-123"]}}})

        result = get_account_type("some_id")

        self.assertEqual(result, AccountType.APPLE)

    @mock.patch("requests.get")
    def test_get_account_type_should_return_unknown_for_unknown_provider(self, mock_get):
        mock_get.return_value = MockJsonResponse({"credentials": {"oidc": {"identifiers": ["123"]}}})

        result = get_account_type("some_id")

        self.assertEqual(result, AccountType.UNKNOWN)

    @mock.patch("requests.get")
    def test_get_account_type_should_return_email_for_non_oidc_account(self, mock_get):
        mock_get.return_value = MockJsonResponse({})

        result = get_account_type("some_id")

        self.assertEqual(result, AccountType.EMAIL)

    @mock.patch("requests.get")
    def test_get_account_type_should_raise_request_error(self, mock_get):
        mock_get.side_effect = HTTPError(response=type("Response", (object,), {"status_code": 500}))

        with self.assertRaises(HTTPError):
            get_account_type("some_id")
