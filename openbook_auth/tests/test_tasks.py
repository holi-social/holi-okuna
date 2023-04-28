import json
import pytest
from datetime import datetime
from unittest import mock
from django.test import Client

from django.test import TestCase
from django_rq import get_queue
from requests.models import Response
from rq.job import Job

from openbook import settings
from openbook_auth.models import User
from openbook_auth.tasks import update_ory_user
from openbook_common.tests.helpers import make_user


@pytest.fixture(scope="session")
def client():
    return Client()


@pytest.fixture(autouse=True)
def user(db, django_user_model):
    return make_user()


@pytest.mark.django_db
class TestUpdateOryUser:
    @mock.patch("requests.patch")
    def test_update_ory_user_success(self, mock_patch, user):
        json_body = [
            {"op": "replace", "path": "/traits/given_name", "value": user.profile.name},
            {"op": "replace", "path": "/traits/family_name", "value": user.profile.last_name},
            {
                "op": "replace",
                "path": "/traits/name",
                "value": user.profile.full_name(),
            },
        ]
        response_content = json.dumps(
            {
                "created_at": "2019-08-24T14:15:22Z",
                "credentials": {},
                "id": user.username,
                "state": "active",
                "traits": {
                    "email": user.email,
                    "name": {"first": user.profile.name, "last": user.profile.last_name},
                },
                "updated_at": str(datetime.now()),
            }
        )
        response = Response()
        response.status_code = 200
        response._content = str.encode(response_content)
        mock_patch.return_value = response

        job: Job = update_ory_user.delay(user.id)

        mock_patch.assert_called_once_with(
            f"{settings.ORY_BASE_URL}/admin/identities/{user.username}",
            headers={"Authorization": f"Bearer {settings.ORY_ACCESS_TOKEN}"},
            json=json_body,
        )
        assert not job.is_failed
        assert job.is_finished
        assert job.result is None

    @mock.patch("requests.patch")
    def test_update_ory_user_failure_user_not_exist(self, mock_patch, user):
        json_body = [
            {"op": "replace", "path": "/traits/given_name", "value": user.profile.name},
            {"op": "replace", "path": "/traits/family_name", "value": user.profile.last_name},
            {
                "op": "replace",
                "path": "/traits/name",
                "value": user.profile.full_name(),
            },
        ]
        response_content = json.dumps(
            {"error": {"code": 404, "status": "Not Found", "message": "Unable to locate the resource"}}
        )
        response = Response()
        response.status_code = 404
        response._content = str.encode(response_content)
        mock_patch.return_value = response

        job: Job = update_ory_user.delay(user.id)

        mock_patch.assert_called_once_with(
            f"{settings.ORY_BASE_URL}/admin/identities/{user.username}",
            headers={"Authorization": f"Bearer {settings.ORY_ACCESS_TOKEN}"},
            json=json_body,
        )
        assert job.is_failed
        assert not job.is_finished
        assert job.result is None

    @mock.patch("requests.patch")
    def test_update_ory_user_failure_bad_request(self, mock_patch, user):
        json_body = [
            {"op": "replace", "path": "/traits/given_name", "value": user.profile.name},
            {"op": "replace", "path": "/traits/family_name", "value": user.profile.last_name},
            {
                "op": "replace",
                "path": "/traits/name",
                "value": user.profile.full_name(),
            },
        ]
        response_content = json.dumps({"error": {"code": 400, "status": "Bad request", "message": "Unsupported"}})
        response = Response()
        response.status_code = 400
        response._content = str.encode(response_content)
        mock_patch.return_value = response

        job: Job = update_ory_user.delay(user.id)

        mock_patch.assert_called_once_with(
            f"{settings.ORY_BASE_URL}/admin/identities/{user.username}",
            headers={"Authorization": f"Bearer {settings.ORY_ACCESS_TOKEN}"},
            json=json_body,
        )
        assert job.is_failed
        assert not job.is_finished
        assert job.result is None
