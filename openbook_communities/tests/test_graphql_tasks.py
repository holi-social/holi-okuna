import copy
import json
import logging
from datetime import timedelta
from typing import Callable
from uuid import uuid4
from unittest import mock

import pytest
from asgiref.sync import async_to_sync
from benedict import benedict
from django.contrib.auth.models import AnonymousUser
from django.contrib.gis import geos
from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.management import call_command
from django.test import AsyncClient
from django.utils import timezone
from faker import Faker
from strawberry.types import ExecutionResult

from openbook.graphql_schema import schema
from openbook.tests.test_data import geolocation_geometry
from openbook_common.enums import VisibilityType
from openbook_common.tests.helpers import (
    assert_is_unauthorized,
    make_community,
    make_community_task,
    make_skill,
    make_skills,
    make_user,
    simple_jpeg_bytes,
    assert_is_forbidden,
    assert_is_404,
)

logger = logging.getLogger(__name__)


@pytest.fixture(scope="session")
def client():
    return AsyncClient()


@pytest.fixture(scope="session")
def django_db_setup(django_db_setup, django_db_blocker):
    with django_db_blocker.unblock():
        call_command("loaddata", "openbook_moderation/fixtures/moderation_categories.json")


@pytest.mark.django_db
class TestTasks:
    @mock.patch("openbook_communities.schema.mutations.publish_task_created_event")
    def test_can_not_create_task_if_not_admin_or_member(self, mock_publish_task_created_event):
        user = make_user()
        community = make_community()

        skill = make_skill()

        create_task_mutation = """
            mutation test($input: CreateTaskInput!) {
                createTask(input: $input) {
                    id
                    name
                }
            }
            """

        valid_input = {
            "spaceId": str(community.id),
            "name": "Valid name",
            "description": "Valid description",
            "visibility": "MEMBERS",
            "locationType": "HYBRID",
            "regularity": "REGULARLY",
            "duration": "INDETERMINATE",
            "contactEmail": "email@email.com",
            "skills": [str(skill.id)],
            "slotsAvailable": 1,
            "location": "Hamburg, Germany",
            "contactPhone": "+49176176176176",
        }

        response = async_to_sync(schema.execute)(
            create_task_mutation,
            variable_values={"input": valid_input},
            context_value=benedict({"request": {"user": user}}),
        )

        field_errors = json.loads(response.errors[0].extensions["errors"])

        assert field_errors[0]["message"] in "You cannot add a task to a community you are not a member of"
        mock_publish_task_created_event.assert_not_called()

    @mock.patch("openbook_communities.schema.mutations.publish_task_created_event")
    def test_can_not_create_public_task_if_not_admin(self, mock_publish_task_created_event):
        user = make_user()
        community = make_community()
        community.add_member(user)

        skill = make_skill()

        create_task_mutation = """
                mutation test($input: CreateTaskInput!) {
                    createTask(input: $input) {
                        id
                        name
                    }
                }
                """

        valid_input = {
            "spaceId": str(community.id),
            "name": "Valid name",
            "description": "Valid description",
            "visibility": "PUBLIC",
            "locationType": "HYBRID",
            "regularity": "REGULARLY",
            "duration": "INDETERMINATE",
            "contactEmail": "email@email.com",
            "skills": [str(skill.id)],
            "slotsAvailable": 1,
            "location": "Hamburg, Germany",
            "contactPhone": "+49176176176176",
        }

        response = async_to_sync(schema.execute)(
            create_task_mutation,
            variable_values={"input": valid_input},
            context_value=benedict({"request": {"user": user}}),
        )

        field_errors = json.loads(response.errors[0].extensions["errors"])

        assert field_errors[0]["message"] in "Only administrators can add public tasks"
        mock_publish_task_created_event.assert_not_called()

    @mock.patch("openbook_communities.schema.mutations.publish_task_created_event")
    def test_can_not_update_task_missing_required_fields(self, mock_publish_task_created_event):
        user = make_user()

        community = make_community(creator=user)
        task = make_community_task(community)

        update_task_mutation = """
            mutation test($input: UpdateTaskInput!) {
                updateTask(input: $input) {
                    id
                }
            }
            """

        valid_input = {
            "taskId": str(task.id),
            "spaceId": str(community.id),
            "name": "Valid name",
            "description": "Valid description",
            "visibility": "MEMBERS",
            "locationType": "HYBRID",
            "regularity": "REGULARLY",
            "contactEmail": "email@email.com",
        }
        expected_errors = {
            "taskId": "Field 'taskId' of required type 'UUID!' was not provided.",
            "name": "Field 'name' of required type 'String!' was not provided.",
            "description": "Field 'description' of required type 'String!' was not provided.",
            "spaceId": "Field 'spaceId' of required type 'UUID!' was not provided.",
            "visibility": "Field 'visibility' of required type 'VisibilityType!' was not provided.",
            "locationType": "Field 'locationType' of required type 'LocationType!' was not provided.",
            "regularity": "Field 'regularity' of required type 'Regularity!' was not provided.",
            "contactEmail": "Field 'contactEmail' of required type 'String!' was not provided.",
        }
        valid_input_keys = valid_input.keys()

        for input_key in valid_input_keys:
            test_input = copy.copy(valid_input)
            test_input.pop(input_key)
            response = async_to_sync(schema.execute)(
                update_task_mutation,
                context_value=benedict({"request": {"user": user}}),
                variable_values={"input": test_input},
            )

            assert expected_errors[input_key] in str(response.errors[0].message)
            assert (response.data["updateTask"] if response.data else response.data) is None

        mock_publish_task_created_event.assert_not_called()

    @mock.patch("openbook_communities.schema.mutations.publish_task_created_event")
    def test_validates_task_before_update(self, mock_publish_task_created_event):
        user = make_user()

        community = make_community(creator=user)
        task = make_community_task(community)
        skill = make_skill()

        update_task_mutation = """
            mutation test($input: UpdateTaskInput!) {
                updateTask(input: $input) {
                    id
                }
            }
            """

        non_existent_skill_id = str(uuid4())

        valid_input = {
            "taskId": str(task.id),
            "spaceId": str(community.id),
            "name": "Valid name",
            "description": "Valid description",
            "visibility": "MEMBERS",
            "locationType": "HYBRID",
            "regularity": "REGULARLY",
            "duration": "INDETERMINATE",
            "contactEmail": "email@email.com",
            "skills": [str(skill.id)],
            "slotsAvailable": 1,
            "location": "Hamburg, Germany",
            "contactPhone": "+49176176176176",
        }

        expectedErrors = [
            {"field": "taskId", "value": str(uuid4()), "expected_error": "No task with the provided id exists."},
            {"field": "spaceId", "value": str(uuid4()), "expected_error": "No community with the provided id exists."},
            {"field": "name", "value": "c", "expected_code": "min_length"},
            {"field": "name", "value": "c" * 400, "expected_code": "max_length"},
            {"field": "description", "value": "c" * 2000, "expected_code": "max_length"},
            {"field": "locationType", "value": None, "expected_error": "Expected non-nullable type"},
            {"field": "regularity", "value": None, "expected_error": "Expected non-nullable type"},
            {"field": "contactEmail", "value": None, "expected_error": "Expected non-nullable type"},
            {"field": "contactPhone", "value": "c" * 500, "expected_code": "max_length"},
            {
                "field": "skills",
                "value": [non_existent_skill_id],
                "expected_error": f"No skill with the id '{non_existent_skill_id}' found.",
            },
            {
                "field": "skillsV2",
                "value": ["unknown"],
                "expected_error": "SkillV2 'unknown' does not exist.",
            },
        ]

        for testCase in expectedErrors:
            response = async_to_sync(schema.execute)(
                update_task_mutation,
                context_value=benedict({"request": {"user": user}}),
                variable_values={"input": valid_input | {testCase["field"]: testCase["value"]}},
            )

            if "expected_code" in testCase:
                field_errors = json.loads(response.errors[0].extensions["errors"])
                assert testCase["expected_code"] == field_errors[testCase["field"]][0]["code"]
            else:
                assert testCase["expected_error"] in str(response.errors[0].message)
            assert (response.data["createTask"] if response.data else response.data) is None

        mock_publish_task_created_event.assert_not_called()

    @mock.patch("openbook_communities.schema.mutations.publish_task_updated_event")
    def test_can_update_task(self, mock_publish_task_updated_event):
        user = make_user()

        community = make_community(creator=user)
        task = make_community_task(community)
        [skill, skill2] = make_skills(2)
        expected_skills_v2 = [skill.slug]

        update_task_mutation = """
            mutation test($input: UpdateTaskInput!) {
                updateTask(input: $input) {
                    id
                    name
                    description
                    visibility
                    thumbnail
                    thumbnailBlurhash
                    skillsV2
                }
            }
            """

        valid_name = "Valid name"
        valid_description = "Valid description"
        valid_visibility = "MEMBERS"
        valid_thumbnail = SimpleUploadedFile(name="thumbnail.jpg", content=simple_jpeg_bytes)

        valid_input = {
            "taskId": str(task.id),
            "spaceId": str(community.id),
            "name": valid_name,
            "description": valid_description,
            "visibility": valid_visibility,
            "locationType": "HYBRID",
            "regularity": "REGULARLY",
            "duration": "INDETERMINATE",
            "contactEmail": "email@email.com",
            "skills": [str(skill.id)],
            "slotsAvailable": 1,
            "location": "Hamburg, Germany",
            "contactPhone": "+49176176176176",
            "thumbnail": valid_thumbnail,
        }

        response = async_to_sync(schema.execute)(
            update_task_mutation,
            context_value=benedict({"request": {"user": user}}),
            variable_values={"input": valid_input},
        )

        assert response.errors is None

        updateTask = response.data["updateTask"]
        assert "id" in updateTask
        assert valid_name == updateTask["name"]
        assert valid_description == updateTask["description"]
        assert valid_visibility == updateTask["visibility"]
        assert "thumbnail.jpg" in updateTask["thumbnail"]
        assert updateTask["thumbnailBlurhash"] is not None
        assert expected_skills_v2 == updateTask["skillsV2"]

        valid_name = "New valid name"
        valid_description = "New valid description"
        valid_visibility = "PUBLIC"

        valid_input = {
            "taskId": str(task.id),
            "spaceId": str(community.id),
            "name": valid_name,
            "description": valid_description,
            "visibility": valid_visibility,
            "locationType": "HYBRID",
            "regularity": "REGULARLY",
            "duration": "INDETERMINATE",
            "contactEmail": "email@email.com",
            "thumbnail": None,
            "slotsAvailable": 1,
            "skillsV2": [skill2.slug],
        }

        mock_publish_task_updated_event.assert_called_once()
        mock_publish_task_updated_event.reset_mock()

        response = async_to_sync(schema.execute)(
            update_task_mutation,
            context_value=benedict({"request": {"user": user}}),
            variable_values={"input": valid_input},
        )

        assert response.errors is None

        updateTask = response.data["updateTask"]
        assert "id" in updateTask
        assert valid_name == updateTask["name"]
        assert valid_description == updateTask["description"]
        assert valid_visibility == updateTask["visibility"]
        assert updateTask["thumbnail"] is None
        assert updateTask["thumbnailBlurhash"] is None
        assert [skill2.slug] == updateTask["skillsV2"]

        mock_publish_task_updated_event.assert_called_once()

    @mock.patch("openbook_communities.schema.mutations.publish_task_updated_event")
    def test_can_update_members_only_task_if_collaborator(self, mock_publish_task_updated_event):
        user = make_user()

        community = make_community()
        community.add_member(user=user)
        task = make_community_task(community)
        skill = make_skill()

        update_task_mutation = """
            mutation test($input: UpdateTaskInput!) {
                updateTask(input: $input) {
                    id
                    name
                    description
                    visibility
                    thumbnail
                    thumbnailBlurhash
                }
            }
            """

        valid_name = "Valid name"
        valid_description = "Valid description"
        valid_visibility = "MEMBERS"
        valid_thumbnail = SimpleUploadedFile(name="thumbnail.jpg", content=simple_jpeg_bytes)

        valid_input = {
            "taskId": str(task.id),
            "spaceId": str(community.id),
            "name": valid_name,
            "description": valid_description,
            "visibility": valid_visibility,
            "locationType": "HYBRID",
            "regularity": "REGULARLY",
            "duration": "INDETERMINATE",
            "contactEmail": "email@email.com",
            "skills": [str(skill.id)],
            "slotsAvailable": 1,
            "location": "Hamburg, Germany",
            "contactPhone": "+49176176176176",
            "thumbnail": valid_thumbnail,
        }

        response = async_to_sync(schema.execute)(
            update_task_mutation,
            context_value=benedict({"request": {"user": user}}),
            variable_values={"input": valid_input},
        )

        assert response.errors is None

        updateTask = response.data["updateTask"]
        assert "id" in updateTask
        assert valid_name == updateTask["name"]
        assert valid_description == updateTask["description"]
        assert valid_visibility == updateTask["visibility"]
        assert "thumbnail.jpg" in updateTask["thumbnail"]
        assert updateTask["thumbnailBlurhash"] is not None

        mock_publish_task_updated_event.assert_called_once()
        mock_publish_task_updated_event.reset_mock()

        valid_name = "New valid name"
        valid_description = "New valid description"
        valid_visibility = "PUBLIC"

        valid_input = {
            "taskId": str(task.id),
            "spaceId": str(community.id),
            "name": valid_name,
            "description": valid_description,
            "visibility": valid_visibility,
            "locationType": "HYBRID",
            "regularity": "REGULARLY",
            "duration": "INDETERMINATE",
            "contactEmail": "email@email.com",
            "thumbnail": None,
            "slotsAvailable": 1,
        }

        response = async_to_sync(schema.execute)(
            update_task_mutation,
            context_value=benedict({"request": {"user": user}}),
            variable_values={"input": valid_input},
        )

        assert response.errors is None

        updateTask = response.data["updateTask"]
        assert "id" in updateTask
        assert valid_name == updateTask["name"]
        assert valid_description == updateTask["description"]
        assert valid_visibility == updateTask["visibility"]
        assert updateTask["thumbnail"] is None
        assert updateTask["thumbnailBlurhash"] is None

        mock_publish_task_updated_event.assert_called_once()

    @mock.patch("openbook_communities.schema.mutations.publish_task_updated_event")
    def test_can_not_update_task_if_not_logged_in(self, mock_publish_task_updated_event):
        community = make_community()
        task = make_community_task(community)
        skill = make_skill()

        update_task_mutation = """
            mutation test($input: UpdateTaskInput!) {
                updateTask(input: $input) {
                    id
                    name
                }
            }
            """

        valid_input = {
            "taskId": str(task.id),
            "spaceId": str(community.id),
            "name": "Valid name",
            "description": "Valid description",
            "visibility": "MEMBERS",
            "locationType": "HYBRID",
            "regularity": "REGULARLY",
            "duration": "INDETERMINATE",
            "contactEmail": "email@email.com",
            "skills": [str(skill.id)],
            "slotsAvailable": 1,
            "location": "Hamburg, Germany",
            "contactPhone": "+49176176176176",
        }

        response = async_to_sync(schema.execute)(
            update_task_mutation,
            variable_values={"input": valid_input},
            context_value=benedict({"request": {"user": AnonymousUser}}),
        )

        assert_is_unauthorized(response)

        mock_publish_task_updated_event.assert_not_called()

    @mock.patch("openbook_communities.schema.mutations.publish_task_updated_event")
    def test_can_not_update_task_if_not_admin_or_member(self, mock_publish_task_updated_event):
        user = make_user()
        community = make_community()
        skill = make_skill()
        task = make_community_task(community)

        update_task_mutation = """
            mutation test($input: UpdateTaskInput!) {
                updateTask(input: $input) {
                    id
                    name
                }
            }
            """

        valid_input = {
            "taskId": str(task.id),
            "spaceId": str(community.id),
            "name": "Valid name",
            "description": "Valid description",
            "visibility": "MEMBERS",
            "locationType": "HYBRID",
            "regularity": "REGULARLY",
            "duration": "INDETERMINATE",
            "contactEmail": "email@email.com",
            "skills": [str(skill.id)],
            "slotsAvailable": 1,
            "location": "Hamburg, Germany",
            "contactPhone": "+49176176176176",
        }

        response = async_to_sync(schema.execute)(
            update_task_mutation,
            variable_values={"input": valid_input},
            context_value=benedict({"request": {"user": user}}),
        )

        assert response.data is None

        field_errors = json.loads(response.errors[0].extensions["errors"])

        assert field_errors[0]["message"] in "You cannot update a task of a community you are not a member of"

        mock_publish_task_updated_event.assert_not_called()

    @mock.patch("openbook_communities.schema.mutations.publish_task_updated_event")
    def test_can_not_update_public_task_if_not_admin(self, mock_publish_task_updated_event):
        user = make_user()
        community = make_community()
        community.add_member(user=user)
        skill = make_skill()
        task = make_community_task(community, visibility=VisibilityType.PUBLIC)

        update_task_mutation = """
                mutation test($input: UpdateTaskInput!) {
                    updateTask(input: $input) {
                        id
                        name
                    }
                }
                """

        valid_input = {
            "taskId": str(task.id),
            "spaceId": str(community.id),
            "name": "Valid name",
            "description": "Valid description",
            "visibility": "MEMBERS",
            "locationType": "HYBRID",
            "regularity": "REGULARLY",
            "duration": "INDETERMINATE",
            "contactEmail": "email@email.com",
            "skills": [str(skill.id)],
            "slotsAvailable": 1,
            "location": "Hamburg, Germany",
            "contactPhone": "+49176176176176",
        }

        response = async_to_sync(schema.execute)(
            update_task_mutation,
            variable_values={"input": valid_input},
            context_value=benedict({"request": {"user": user}}),
        )

        assert response.data is None

        field_errors = json.loads(response.errors[0].extensions["errors"])

        assert field_errors[0]["message"] in "Only administrators can update public tasks"

        mock_publish_task_updated_event.assert_not_called()

    @mock.patch("openbook_communities.schema.mutations.publish_task_deleted_event")
    def test_can_not_delete_task_if_member(self, mock_publish_task_deleted_event):
        user = make_user()
        community = make_community()
        task = make_community_task(community)

        delete_task_mutation = """
            mutation test($id: UUID!) {
                deleteTask(id: $id) {
                    success
                }
            }
            """

        response = async_to_sync(schema.execute)(
            delete_task_mutation,
            context_value=benedict({"request": {"user": user}}),
            variable_values={"id": str(task.id)},
        )

        assert response.data is None
        assert "You cannot delete a task of a community you are not a member of" in str(
            response.errors[0].extensions["errors"]
        )

        mock_publish_task_deleted_event.assert_not_called()

    @mock.patch("openbook_communities.schema.mutations.publish_task_deleted_event")
    def test_can_not_delete_public_task_if_not_admin(self, mock_publish_task_deleted_event):
        user = make_user()
        community = make_community()
        community.add_member(user=user)
        task = make_community_task(community, visibility=VisibilityType.PUBLIC)

        delete_task_mutation = """
                mutation test($id: UUID!) {
                    deleteTask(id: $id) {
                        success
                    }
                }
                """

        response = async_to_sync(schema.execute)(
            delete_task_mutation,
            context_value=benedict({"request": {"user": user}}),
            variable_values={"id": str(task.id)},
        )

        assert response.data is None
        assert "Only administrators can delete public tasks" in str(response.errors[0].extensions["errors"])

        mock_publish_task_deleted_event.assert_not_called()

    @mock.patch("openbook_communities.schema.mutations.publish_task_deleted_event")
    def test_can_not_delete_task_if_not_logged_in(self, mock_publish_task_deleted_event):
        community = make_community()
        task = make_community_task(community)

        delete_task_mutation = """
            mutation test($id: UUID!) {
                deleteTask(id: $id) {
                    success
                }
            }
            """

        response = async_to_sync(schema.execute)(
            delete_task_mutation,
            variable_values={"id": str(task.id)},
            context_value=benedict({"request": {"user": AnonymousUser}}),
        )

        assert_is_unauthorized(response)

        mock_publish_task_deleted_event.assert_not_called()

    @mock.patch("openbook_communities.schema.mutations.publish_task_deleted_event")
    def test_can_delete_task(self, mock_publish_task_deleted_event):
        user = make_user()
        community = make_community(creator=user)
        task = make_community_task(community)

        delete_task_mutation = """
            mutation test($id: UUID!) {
                deleteTask(id: $id) {
                    success
                }
            }
            """

        response = async_to_sync(schema.execute)(
            delete_task_mutation,
            variable_values={"id": str(task.id)},
            context_value=benedict({"request": {"user": user}}),
        )

        assert response.data["deleteTask"]["success"] is True
        assert response.errors is None

        mock_publish_task_deleted_event.assert_called_once()

    @mock.patch("openbook_communities.schema.mutations.publish_task_deleted_event")
    def test_can_delete_members_only_task_if_collaborator(self, mock_publish_task_deleted_event):
        user = make_user()
        community = make_community()
        community.add_member(user=user)
        task = make_community_task(community)

        delete_task_mutation = """
            mutation test($id: UUID!) {
                deleteTask(id: $id) {
                    success
                }
            }
            """

        response = async_to_sync(schema.execute)(
            delete_task_mutation,
            variable_values={"id": str(task.id)},
            context_value=benedict({"request": {"user": user}}),
        )

        assert response.data["deleteTask"]["success"] is True
        assert response.errors is None

        mock_publish_task_deleted_event.assert_called_once()

    @mock.patch("openbook_communities.schema.mutations.publish_task_created_event")
    def test_validates_task_before_creation(self, mock_publish_task_created_event):
        user = make_user()

        community = make_community(creator=user)
        skill = make_skill()

        create_task_mutation = """
            mutation test($input: CreateTaskInput!) {
                createTask(input: $input) {
                    id
                }
            }
            """

        non_existent_skill_id = str(uuid4())

        valid_input = {
            "spaceId": str(community.id),
            "name": "Valid name",
            "description": "Valid description",
            "visibility": "MEMBERS",
            "locationType": "HYBRID",
            "regularity": "REGULARLY",
            "duration": "INDETERMINATE",
            "contactEmail": "email@email.com",
            "skills": [str(skill.id)],
            "slotsAvailable": 1,
            "location": "Hamburg, Germany",
            "contactPhone": "+49176176176176",
        }

        expectedErrors = [
            {"field": "spaceId", "value": str(uuid4()), "expected_error": "No community with the provided id exists."},
            {"field": "name", "value": "c", "expected_code": "min_length"},
            {"field": "name", "value": "c" * 400, "expected_code": "max_length"},
            {"field": "description", "value": "c" * 2000, "expected_code": "max_length"},
            {"field": "locationType", "value": None, "expected_error": "Expected non-nullable type"},
            {"field": "regularity", "value": None, "expected_error": "Expected non-nullable type"},
            {"field": "contactEmail", "value": None, "expected_error": "Expected non-nullable type"},
            {"field": "contactPhone", "value": "c" * 500, "expected_code": "max_length"},
            {
                "field": "skills",
                "value": [non_existent_skill_id],
                "expected_error": f"No skill with the id '{non_existent_skill_id}' found.",
            },
            {
                "field": "skillsV2",
                "value": ["unknown"],
                "expected_error": "SkillV2 'unknown' does not exist.",
            },
        ]

        for testCase in expectedErrors:
            response = async_to_sync(schema.execute)(
                create_task_mutation,
                context_value=benedict({"request": {"user": user}}),
                variable_values={"input": valid_input | {testCase["field"]: testCase["value"]}},
            )

            if "expected_code" in testCase:
                field_errors = json.loads(response.errors[0].extensions["errors"])
                assert testCase["expected_code"] == field_errors[testCase["field"]][0]["code"]
            else:
                assert testCase["expected_error"] in str(response.errors[0].message)
            assert (response.data["createTask"] if response.data else response.data) is None

        mock_publish_task_created_event.assert_not_called()

    @mock.patch("openbook_communities.schema.mutations.publish_task_created_event")
    def test_can_create_task(self, mock_publish_task_created_event):
        user = make_user()

        community = make_community(creator=user)
        skill = make_skill()
        expected_skills_v2 = [skill.slug]

        create_task_mutation = """
            mutation test($input: CreateTaskInput!) {
                createTask(input: $input) {
                    id
                    name
                    description
                    visibility
                    skillsV2
                }
            }
            """

        valid_name = "Valid name"
        valid_description = "Valid description"
        valid_visibility = "MEMBERS"

        valid_input = {
            "spaceId": str(community.id),
            "name": valid_name,
            "description": valid_description,
            "visibility": valid_visibility,
            "locationType": "HYBRID",
            "regularity": "REGULARLY",
            "duration": "INDETERMINATE",
            "contactEmail": "email@email.com",
            "skills": [str(skill.id)],
            "slotsAvailable": 1,
            "location": "Hamburg, Germany",
            "contactPhone": "+49176176176176",
        }

        response = async_to_sync(schema.execute)(
            create_task_mutation,
            context_value=benedict({"request": {"user": user}}),
            variable_values={"input": valid_input},
        )

        assert response.errors is None

        created_task = response.data["createTask"]
        assert "id" in created_task
        assert valid_name == created_task["name"]
        assert valid_description == created_task["description"]
        assert valid_visibility == created_task["visibility"]
        assert expected_skills_v2 == created_task["skillsV2"]

        mock_publish_task_created_event.assert_called_once()

    # make duration required after FE clients that don't send this for updates/creation of task are phased out (1.54+?)
    # remove this then
    def test_can_create_task_without_timing_metadata_as_older__client(self):
        user = make_user()

        community = make_community(creator=user)
        skill = make_skill()

        create_task_mutation = """
            mutation test($input: CreateTaskInput!) {
                createTask(input: $input) {
                    id
                    name
                    description
                    visibility
                    skillsV2
                }
            }
            """

        valid_name = "Valid name"
        valid_description = "Valid description"
        valid_visibility = "MEMBERS"
        valid_input = {
            "spaceId": str(community.id),
            "name": valid_name,
            "description": valid_description,
            "visibility": valid_visibility,
            "locationType": "HYBRID",
            "regularity": "REGULARLY",
            "contactEmail": "email@email.com",
            "skills": [str(skill.id)],
            "slotsAvailable": 1,
            "location": "Hamburg, Germany",
            "contactPhone": "+49176176176176",
        }

        response = async_to_sync(schema.execute)(
            create_task_mutation,
            context_value=benedict({"request": {"user": user}}),
            variable_values={"input": valid_input},
        )

        assert response.errors is None
        created_task = response.data["createTask"]
        assert "id" in created_task

    @mock.patch("openbook_communities.schema.mutations.publish_task_created_event")
    def test_can_create_task_with_skills_v2(self, mock_publish_task_created_event):
        user = make_user()

        community = make_community(creator=user)
        skills_v2 = [skill.slug for skill in make_skills(2)]

        create_task_mutation = """
            mutation test($input: CreateTaskInput!) {
                createTask(input: $input) {
                    id
                    skillsV2
                }
            }
            """

        valid_name = "Valid name"
        valid_description = "Valid description"
        valid_visibility = "MEMBERS"

        valid_input = {
            "spaceId": str(community.id),
            "name": valid_name,
            "description": valid_description,
            "visibility": valid_visibility,
            "locationType": "HYBRID",
            "regularity": "REGULARLY",
            "duration": "INDETERMINATE",
            "contactEmail": "email@email.com",
            "skillsV2": skills_v2,
            "slotsAvailable": 1,
            "location": "Hamburg, Germany",
            "contactPhone": "+49176176176176",
        }

        response = async_to_sync(schema.execute)(
            create_task_mutation,
            context_value=benedict({"request": {"user": user}}),
            variable_values={"input": valid_input},
        )

        assert response.errors is None

        created_task = response.data["createTask"]
        assert skills_v2 == created_task["skillsV2"]

        mock_publish_task_created_event.assert_called_once()

    @mock.patch("openbook_communities.schema.mutations.publish_task_created_event")
    def test_can_create_members_only_task_if_collaborator(self, mock_publish_task_created_event):
        user = make_user()

        community = make_community()
        community.add_member(user=user)

        skill = make_skill()

        create_task_mutation = """
            mutation test($input: CreateTaskInput!) {
                createTask(input: $input) {
                    id
                    name
                    description
                    visibility
                }
            }
            """

        valid_name = "Valid name"
        valid_description = "Valid description"
        valid_visibility = "MEMBERS"

        valid_input = {
            "spaceId": str(community.id),
            "name": valid_name,
            "description": valid_description,
            "visibility": valid_visibility,
            "locationType": "HYBRID",
            "regularity": "REGULARLY",
            "duration": "INDETERMINATE",
            "contactEmail": "email@email.com",
            "skills": [str(skill.id)],
            "slotsAvailable": 1,
            "location": "Hamburg, Germany",
            "contactPhone": "+49176176176176",
        }

        response = async_to_sync(schema.execute)(
            create_task_mutation,
            context_value=benedict({"request": {"user": user}}),
            variable_values={"input": valid_input},
        )

        assert response.errors is None

        added_collaboration_tool = response.data["createTask"]
        assert "id" in added_collaboration_tool
        assert valid_name == added_collaboration_tool["name"]
        assert valid_description == added_collaboration_tool["description"]
        assert valid_visibility == added_collaboration_tool["visibility"]

        mock_publish_task_created_event.assert_called_once()

    @mock.patch("openbook_communities.schema.mutations.publish_task_created_event")
    def test_can_not_create_task_if_not_logged_in(self, mock_publish_task_created_event):
        community = make_community()
        skill = make_skill()

        create_task_mutation = """
            mutation test($input: CreateTaskInput!) {
                createTask(input: $input) {
                    id
                    name
                }
            }
            """

        valid_input = {
            "spaceId": str(community.id),
            "name": "Valid name",
            "description": "Valid description",
            "visibility": "MEMBERS",
            "locationType": "HYBRID",
            "regularity": "REGULARLY",
            "duration": "INDETERMINATE",
            "contactEmail": "email@email.com",
            "skills": [str(skill.id)],
            "slotsAvailable": 1,
            "location": "Hamburg, Germany",
            "contactPhone": "+49176176176176",
        }

        response = async_to_sync(schema.execute)(
            create_task_mutation,
            variable_values={"input": valid_input},
            context_value=benedict({"request": {"user": AnonymousUser}}),
        )

        assert_is_unauthorized(response)

        mock_publish_task_created_event.assert_not_called()

    @mock.patch("openbook_communities.schema.mutations.publish_task_created_event")
    def test_can_not_create_task_missing_required_fields(self, mock_publish_task_created_event):
        user = make_user()

        community = make_community(creator=user)

        create_task_mutation = """
            mutation test($input: CreateTaskInput!) {
                createTask(input: $input) {
                    id
                }
            }
            """

        valid_input = {
            "name": "Valid name",
            "description": "Valid description",
            "spaceId": str(community.id),
            "visibility": "MEMBERS",
            "locationType": "HYBRID",
            "regularity": "REGULARLY",
            "contactEmail": "email@email.com",
        }
        expected_errors = {
            "name": "Field 'name' of required type 'String!' was not provided.",
            "description": "Field 'description' of required type 'String!' was not provided.",
            "spaceId": "Field 'spaceId' of required type 'UUID!' was not provided.",
            "visibility": "Field 'visibility' of required type 'VisibilityType!' was not provided.",
            "locationType": "Field 'locationType' of required type 'LocationType!' was not provided.",
            "regularity": "Field 'regularity' of required type 'Regularity!' was not provided.",
            "contactEmail": "Field 'contactEmail' of required type 'String!' was not provided.",
        }
        valid_input_keys = valid_input.keys()

        for input_key in valid_input_keys:
            test_input = copy.copy(valid_input)
            test_input.pop(input_key)
            response = async_to_sync(schema.execute)(
                create_task_mutation,
                context_value=benedict({"request": {"user": user}}),
                variable_values={"input": test_input},
            )

            assert expected_errors[input_key] in str(response.errors[0].message)
            assert (response.data["createTask"] if response.data else response.data) is None

        mock_publish_task_created_event.assert_not_called()

    def test_anonymous_and_non_members_only_sees_public_tasks_by_space(self):
        user = make_user()
        non_member = make_user()
        space = make_community(creator=user)
        public_task = make_community_task(space, visibility=VisibilityType.PUBLIC)
        make_community_task(space, visibility=VisibilityType.MEMBERS)

        tasks_query = """
            query MyQuery($id: UUID!) {
                tasksBySpaceId(spaceId: $id) {
                    data {
                        id
                    }
                    totalResults
                }
            }
        """
        response = async_to_sync(schema.execute)(
            tasks_query,
            variable_values={"id": str(space.id)},
            context_value=benedict({"request": {"user": AnonymousUser}}),
        )
        assert response.errors is None
        assert response.data["tasksBySpaceId"]["totalResults"] == 1
        assert response.data["tasksBySpaceId"]["data"][0]["id"] == str(public_task.id)

        response = async_to_sync(schema.execute)(
            tasks_query,
            variable_values={"id": str(space.id)},
            context_value=benedict({"request": {"user": non_member}}),
        )
        assert response.errors is None
        assert response.data["tasksBySpaceId"]["totalResults"] == 1
        assert response.data["tasksBySpaceId"]["data"][0]["id"] == str(public_task.id)

    def test_members_sees_private_tasks_by_space(self):
        user = make_user()
        space = make_community(creator=user)
        make_community_task(space, visibility=VisibilityType.PUBLIC)
        make_community_task(space, visibility=VisibilityType.MEMBERS)

        tasks_query = """
            query MyQuery($id: UUID!) {
                tasksBySpaceId(spaceId: $id) {
                    data {
                        id
                    }
                    totalResults
                }
            }
        """
        response = async_to_sync(schema.execute)(
            tasks_query,
            variable_values={"id": str(space.id)},
            context_value=benedict({"request": {"user": user}}),
        )
        assert response.errors is None
        assert response.data["tasksBySpaceId"]["totalResults"] == 2

    def test_anonymous_only_sees_public_tasks_by_id(self):
        user = make_user()
        non_member = make_user()
        space = make_community(creator=user)
        public_task = make_community_task(space, visibility=VisibilityType.PUBLIC)
        private_task = make_community_task(space, visibility=VisibilityType.MEMBERS)

        tasks_query = """
            query MyQuery($id: UUID!) {
                taskById(id: $id) {
                    id
                }
            }
        """
        response = async_to_sync(schema.execute)(
            tasks_query,
            variable_values={"id": str(public_task.id)},
            context_value=benedict({"request": {"user": AnonymousUser}}),
        )
        assert response.errors is None
        assert response.data["taskById"]["id"] == str(public_task.id)

        response = async_to_sync(schema.execute)(
            tasks_query,
            variable_values={"id": str(public_task.id)},
            context_value=benedict({"request": {"user": non_member}}),
        )
        assert response.errors is None
        assert response.data["taskById"]["id"] == str(public_task.id)

        response = async_to_sync(schema.execute)(
            tasks_query,
            variable_values={"id": str(private_task.id)},
            context_value=benedict({"request": {"user": AnonymousUser}}),
        )
        assert_is_forbidden(response)

        response = async_to_sync(schema.execute)(
            tasks_query,
            variable_values={"id": str(private_task.id)},
            context_value=benedict({"request": {"user": non_member}}),
        )
        assert_is_forbidden(response)

        response = async_to_sync(schema.execute)(
            tasks_query,
            variable_values={"id": "00000000-0000-0000-0000-000000000004"},
            context_value=benedict({"request": {"user": AnonymousUser}}),
        )
        assert_is_404(response)

        response = async_to_sync(schema.execute)(
            tasks_query,
            variable_values={"id": "00000000-0000-0000-0000-000000000004"},
            context_value=benedict({"request": {"user": non_member}}),
        )
        assert_is_404(response)

    def test_members_see_private_tasks(self):
        user = make_user()
        space = make_community(creator=user)
        public_task = make_community_task(space, visibility=VisibilityType.PUBLIC)
        private_task = make_community_task(space, visibility=VisibilityType.MEMBERS)

        tasks_query = """
            query MyQuery($id: UUID!) {
                taskById(id: $id) {
                    id
                }
            }
        """
        response = async_to_sync(schema.execute)(
            tasks_query,
            variable_values={"id": str(public_task.id)},
            context_value=benedict({"request": {"user": user}}),
        )
        assert response.errors is None
        assert response.data["taskById"]["id"] == str(public_task.id)

        response = async_to_sync(schema.execute)(
            tasks_query,
            variable_values={"id": str(private_task.id)},
            context_value=benedict({"request": {"user": user}}),
        )
        assert response.errors is None
        assert response.data["taskById"]["id"] == str(private_task.id)

        response = async_to_sync(schema.execute)(
            tasks_query,
            variable_values={"id": "00000000-0000-0000-0000-000000000004"},
            context_value=benedict({"request": {"user": user}}),
        )
        assert_is_404(response)

    def test_deleted_tasks_cannot_be_fetched(self) -> None:
        user = make_user()
        space = make_community(creator=user)

        deleted_task = make_community_task(space, is_deleted=True)

        tasks_query = """
            query Task($id: UUID!) {
                taskById(id: $id) {
                    id
                }
            }
        """

        response = async_to_sync(schema.execute)(
            tasks_query,
            variable_values={"id": str(deleted_task.id)},
            context_value=benedict({"request": {"user": user}}),
        )

        assert_is_404(response)

    def test_deleted_tasks_are_not_returned_by_space_id(self) -> None:
        user = make_user()
        space = make_community(creator=user)

        _public_task = make_community_task(space, visibility=VisibilityType.PUBLIC)
        deleted_task = make_community_task(space, is_deleted=True)

        query = """
            query TasksBySpace($spaceId: UUID!) {
                tasksBySpaceId(spaceId: $spaceId) {
                    data {
                        id
                    }
                    
                    totalResults
                }
            }
        """

        response = async_to_sync(schema.execute)(
            query, variable_values={"spaceId": str(space.id)}, context_value=benedict({"request": {"user": user}})
        )

        assert response.errors is None
        assert str(deleted_task.id) not in [task["id"] for task in response.data["tasksBySpaceId"]["data"]]
        assert response.data["tasksBySpaceId"]["totalResults"] == 1

    def test_deleted_tasks_are_not_returned_with_space(self) -> None:
        user = make_user()
        space = make_community(creator=user)

        _public_task = make_community_task(space, visibility=VisibilityType.PUBLIC)
        deleted_task = make_community_task(space, is_deleted=True)

        query = """
            query Space($spaceId: String!) {
                spaceById(idOrName: $spaceId) {
                    id
                    tasks {
                        id
                    }
                }
            }
        """

        response = async_to_sync(schema.execute)(
            query, variable_values={"spaceId": str(space.id)}, context_value=benedict({"request": {"user": user}})
        )

        assert response.errors is None
        assert str(deleted_task.id) not in [task["id"] for task in response.data["spaceById"]["tasks"]]
        assert len(response.data["spaceById"]["tasks"]) == 1

    class FilterExpiredTasksTestData:
        via_space_id = (
            """ 
                query Space($spaceId: String!) {
                    spaceById(idOrName: $spaceId) {
                        id
                        tasks {
                            id
                        }
                    }
                }
            """,
            lambda resp: [task["id"] for task in resp.data["spaceById"]["tasks"]],
        )

        tasks_by_space_id = (
            """
                query Space($spaceId: UUID!) {
                    tasksBySpaceId(spaceId: $spaceId) {
                        data {
                            id
                        }
                    }
                }
            """,
            lambda resp: [task["id"] for task in resp.data["tasksBySpaceId"]["data"]],
        )

        recommended_tasks = (
            """
                query RecommendedTasks {
                    recommendedTasks {
                        data {
                            id
                        }
                    }
                }
            """,
            lambda resp: [task["id"] for task in resp.data["recommendedTasks"]["data"]],
        )

    @pytest.mark.parametrize(
        "query,task_ids_from_response,request_with,should_contain_expired",
        [
            pytest.param(*FilterExpiredTasksTestData.via_space_id, "ANON", False, id="via_space_id_anon_no_expired"),
            pytest.param(*FilterExpiredTasksTestData.via_space_id, "USER", False, id="via_space_id_user_no_expired"),
            pytest.param(
                *FilterExpiredTasksTestData.via_space_id, "ADMIN", True, id="via_space_id_admin_include_expired"
            ),
            pytest.param(
                *FilterExpiredTasksTestData.tasks_by_space_id, "ANON", False, id="tasks_by_space_id_anon_no_expired"
            ),
            pytest.param(
                *FilterExpiredTasksTestData.tasks_by_space_id, "USER", False, id="tasks_by_space_id_user_no_expired"
            ),
            pytest.param(
                *FilterExpiredTasksTestData.tasks_by_space_id,
                "ADMIN",
                True,
                id="tasks_by_space_id_admin_include_expired",
            ),
            pytest.param(
                *FilterExpiredTasksTestData.recommended_tasks,
                "ANON",
                False,
                id="recommended_tasks_anon_no_expired",
            ),
            pytest.param(
                *FilterExpiredTasksTestData.recommended_tasks,
                "USER",
                False,
                id="recommended_tasks_user_no_expired",
            ),
            pytest.param(
                *FilterExpiredTasksTestData.recommended_tasks,
                "ADMIN",
                False,
                id="recommended_tasks_admin_no_expired",
            ),
        ],
    )
    def test_expired_tasks_are_filtered_correctly_on_lists(
        self,
        query: str,
        request_with: str,
        task_ids_from_response: Callable[[ExecutionResult], list[str]],
        should_contain_expired: bool,
    ):
        """
        Given: we have a space with an expired task and a current task
        When: we run a query fetching tasks
        Then: we verify that the business rules regarding filtering out expired tasks are kept
        """
        user = make_user()
        space = make_community(creator=user)

        timeframe_start_date = timezone.now() - timedelta(days=7)
        timeframe_end_date_future = timezone.now() + timedelta(days=3)
        timeframe_end_date_past = timezone.now() - timedelta(days=1)

        current_task = make_community_task(
            space,
            visibility=VisibilityType.PUBLIC,
            timeframe_start_date=timeframe_start_date,
            timeframe_end_date=timeframe_end_date_future,
        )

        expired_task = make_community_task(
            space,
            visibility=VisibilityType.PUBLIC,
            timeframe_start_date=timeframe_start_date,
            timeframe_end_date=timeframe_end_date_past,
        )

        match request_with:
            case "ANON":
                request_user = AnonymousUser
            case "ADMIN":
                request_user = user
            case _:
                request_user = make_user()

        response = async_to_sync(schema.execute)(
            query,
            variable_values={"spaceId": str(space.id)},
            context_value=benedict({"request": {"user": request_user}}),
        )
        response_task_ids = task_ids_from_response(response)

        assert response.errors is None
        assert str(current_task.id) in response_task_ids

        if should_contain_expired:
            assert str(expired_task.id) in response_task_ids
        else:
            assert str(expired_task.id) not in response_task_ids


@pytest.mark.django_db
class TestTaskRecommendations:
    @pytest.fixture(autouse=True)
    def setup(self):
        self.fake = Faker()
        self.user = make_user()
        self.space_owner = make_user()
        self.space = make_community(creator=self.space_owner)
        self.space_deleted_owner = make_user()
        self.space_deleted = make_community(creator=self.space_deleted_owner, is_deleted=True)

    def create_task(self, skills, location_type, geolocation=None, visibility=VisibilityType.PUBLIC, space=None):
        if space is None:
            space = self.space
        return space.creator.create_task(
            geolocation=geolocation,
            skills=skills,
            location_type=location_type,
            visibility=visibility,
            space_id=space.id,
            name=self.fake.text(max_nb_chars=20),
            description=self.fake.text(max_nb_chars=20),
            slots_available=3,
            contact_email="some@email.de",
            regularity="ONE_TIME",
            duration="INDETERMINATE",
        )

    def assert_filtered_tasks(self, filter_options, expected_spaces, total_results=None):
        def transform_space(space):
            return {"id": str(space.id)}

        recommended_tasks_query = """
            query MyQuery($limit: Int, $offset: Int) {
                recommendedTasks(limit: $limit, offset: $offset) {
                    data {
                        id
                    }
                    totalResults
                }
            }
        """

        filter_response = async_to_sync(schema.execute)(
            recommended_tasks_query,
            variable_values=filter_options,
            context_value=benedict({"request": {"user": self.user}}),
        )
        assert filter_response.errors is None
        expected_data = list(map(transform_space, expected_spaces))
        assert filter_response.data["recommendedTasks"]["data"] == expected_data
        if total_results is not None:
            assert filter_response.data["recommendedTasks"]["totalResults"] == total_results

    def test_filters_for_recommended_tasks(self):
        [skill1, skill2, other_skill] = make_skills(3)

        # locations inside geolocation filter
        geolocation1 = geos.Point(8.5541567, 53.5101827, srid=4326)
        # location outside geolocation filter
        geolocation3 = geos.Point(9.76302, 53.5586627, srid=4326)

        task_remote_2_skills = self.create_task(skills=[skill1.id, skill2.id], location_type="REMOTE")
        task_onsite_2_skills = self.create_task(
            skills=[skill1.id, skill2.id], location_type="ONSITE", geolocation=geolocation1
        )
        task_onsite_skill_1 = self.create_task(skills=[skill1.id], location_type="ONSITE", geolocation=geolocation1)
        task_remote_skill_2 = self.create_task(skills=[skill2.id], location_type="REMOTE")
        task_outside_onsite_skill_2 = self.create_task(
            skills=[skill2.id], location_type="ONSITE", geolocation=geolocation3
        )
        task_onsite_other_skill = self.create_task(
            skills=[other_skill.id], location_type="ONSITE", geolocation=geolocation1
        )
        task_onsite_skill_1_and_other_skill = self.create_task(
            skills=[skill1.id, other_skill.id], location_type="ONSITE", geolocation=geolocation1
        )
        task_outside_onsite_other_skill = self.create_task(
            skills=[other_skill.id], location_type="ONSITE", geolocation=geolocation3
        )
        task_remote_other_skill = self.create_task(skills=[other_skill.id], location_type="REMOTE")

        # tasks from moderated spaces are not shown
        self.create_task(space=self.space_deleted, skills=[skill2.id], location_type="REMOTE")

        # moderated tasks are not shown
        moderated_task = self.create_task(skills=[skill2.id], location_type="REMOTE")
        moderated_task.soft_delete()

        # member only tasks are not visible to non-members
        self.create_task(skills=[skill1.id], location_type="REMOTE", visibility=VisibilityType.MEMBERS)

        # when the user has no profile information, the last five tasks are returned
        self.assert_filtered_tasks(
            {},
            [
                task_remote_other_skill,
                task_outside_onsite_other_skill,
                task_onsite_skill_1_and_other_skill,
                task_onsite_other_skill,
                task_outside_onsite_skill_2,
            ],
        )

        self.user.profile.skills.add(skill1)
        self.user.profile.skills.add(skill2)
        self.user.profile.skills_v2 = [skill1.slug, skill2.slug]
        self.user.profile.geolocation = geos.GEOSGeometry(json.dumps(geolocation_geometry))

        self.assert_filtered_tasks(
            {"limit": 10},
            [
                # skill matches and geo matches or remote
                task_onsite_skill_1_and_other_skill,
                task_remote_skill_2,
                task_onsite_skill_1,
                task_onsite_2_skills,
                task_remote_2_skills,
                # only skill matches
                task_outside_onsite_skill_2,
                # only geo matches
                # NOT task_onsite_skill_1_and_other_skill, since it's already found in skill matches and geo matches and there should be no duplicates
                task_onsite_other_skill,
                # everything else
                task_remote_other_skill,
                task_outside_onsite_other_skill,
            ],
        )

    def test_filters_for_recommended_tasks_paging(self):
        [skill1, other_skill] = make_skills(2)
        self.user.profile.skills.add(skill1)
        self.user.profile.skills_v2 = [skill1.slug]
        self.user.profile.geolocation = geos.GEOSGeometry(json.dumps(geolocation_geometry))

        # locations inside geolocation filter
        geolocation1 = geos.Point(8.5541567, 53.5101827, srid=4326)
        # location outside geolocation filter
        geolocation3 = geos.Point(9.76302, 53.5586627, srid=4326)
        task_remote_skill1 = self.create_task(skills=[skill1.id], location_type="REMOTE")
        task_onsite_skill1 = self.create_task(skills=[skill1.id], location_type="ONSITE", geolocation=geolocation1)
        task_remote_skill2 = self.create_task(skills=[skill1.id], location_type="REMOTE")
        task_onsite_skill2 = self.create_task(skills=[skill1.id], location_type="ONSITE", geolocation=geolocation1)
        task_other_site_skill1 = self.create_task(skills=[skill1.id], location_type="ONSITE", geolocation=geolocation3)
        task_other_site_skill2 = self.create_task(skills=[skill1.id], location_type="ONSITE", geolocation=geolocation3)
        task_other_site_skill3 = self.create_task(skills=[skill1.id], location_type="ONSITE", geolocation=geolocation3)
        task_onsite_other_skill1 = self.create_task(
            skills=[other_skill.id], location_type="ONSITE", geolocation=geolocation1
        )
        task_onsite_other_skill2 = self.create_task(
            skills=[other_skill.id], location_type="ONSITE", geolocation=geolocation1
        )
        task_onsite_other_skill3 = self.create_task(
            skills=[other_skill.id], location_type="ONSITE", geolocation=geolocation1
        )
        task_outside_onsite_other_skill1 = self.create_task(
            skills=[other_skill.id], location_type="ONSITE", geolocation=geolocation3
        )
        task_remote_other_skill1 = self.create_task(skills=[other_skill.id], location_type="REMOTE")
        task_outside_onsite_other_skill2 = self.create_task(
            skills=[other_skill.id], location_type="ONSITE", geolocation=geolocation3
        )
        task_remote_other_skill2 = self.create_task(skills=[other_skill.id], location_type="REMOTE")

        self.assert_filtered_tasks(
            {"limit": 20},
            [
                # skill matches and geo matches or remote
                task_onsite_skill2,
                task_remote_skill2,
                task_onsite_skill1,
                task_remote_skill1,
                # only skill matches
                task_other_site_skill3,
                task_other_site_skill2,
                task_other_site_skill1,
                # only geo matches
                task_onsite_other_skill3,
                task_onsite_other_skill2,
                task_onsite_other_skill1,
                # everything else
                task_remote_other_skill2,
                task_outside_onsite_other_skill2,
                task_remote_other_skill1,
                task_outside_onsite_other_skill1,
            ],
            14,
        )

        self.assert_filtered_tasks(
            {"limit": 6, "offset": 2},
            [
                # skill matches and geo matches or remote
                task_onsite_skill1,
                task_remote_skill1,
                # only skill matches
                task_other_site_skill3,
                task_other_site_skill2,
                task_other_site_skill1,
                # only geo matches
                task_onsite_other_skill3,
            ],
            14,
        )

        self.assert_filtered_tasks(
            {"limit": 6, "offset": 5},
            [
                task_other_site_skill2,
                task_other_site_skill1,
                # only geo matches
                task_onsite_other_skill3,
                task_onsite_other_skill2,
                task_onsite_other_skill1,
                # everything else
                task_remote_other_skill2,
            ],
            14,
        )
