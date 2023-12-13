import copy
import json
import logging
from uuid import uuid4

import pytest
from asgiref.sync import async_to_sync
from benedict import benedict
from django.contrib.auth.models import AnonymousUser
from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.management import call_command
from django.test import AsyncClient

from openbook.graphql_schema import schema
from openbook_common.enums import VisibilityType
from openbook_common.tests.helpers import (
    assert_is_unauthorized,
    make_community,
    make_community_task,
    make_skill,
    make_user,
    simple_jpeg_bytes,
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
    def test_can_not_create_task_if_not_admin_or_member(self):
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

    def test_can_not_create_public_task_if_not_admin(self):
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

    def test_can_not_update_task_missing_required_fields(self):
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

    def test_validates_task_before_update(self):
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

    def test_can_update_task(self):
        user = make_user()

        community = make_community(creator=user)
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
        assert "" == updateTask["thumbnail"]
        assert updateTask["thumbnailBlurhash"] is None

    def test_can_update_members_only_task_if_collaborator(self):
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
        assert "" == updateTask["thumbnail"]
        assert updateTask["thumbnailBlurhash"] is None

    def test_can_not_update_task_if_not_logged_in(self):
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

    def test_can_not_update_task_if_not_admin_or_member(self):
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

    def test_can_not_update_public_task_if_not_admin(self):
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

    def test_can_not_delete_task_if_member(self):
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

    def test_can_not_delete_public_task_if_not_admin(self):
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

    def test_can_not_delete_task_if_not_logged_in(self):
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

    def test_can_delete_task(self):
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

    def test_can_delete_members_only_task_if_collaborator(self):
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

    def test_validates_task_before_creation(self):
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

    def test_can_create_task(self):
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

        added_collaboration_tool = response.data["createTask"]
        assert "id" in added_collaboration_tool
        assert valid_name == added_collaboration_tool["name"]
        assert valid_description == added_collaboration_tool["description"]
        assert valid_visibility == added_collaboration_tool["visibility"]

    def test_can_create_members_only_task_if_collaborator(self):
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

    def test_can_not_create_task_if_not_logged_in(self):
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

    def test_can_not_create_task_missing_required_fields(self):
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
