import json
import logging
from uuid import uuid4

import pytest
from asgiref.sync import async_to_sync
from benedict import benedict
from django.contrib.auth.models import AnonymousUser
from django.core.management import call_command
from django.test import AsyncClient

from openbook.graphql_schema import schema
from openbook_common.tests.helpers import (
    assert_is_unauthorized,
    make_collaboration_tool,
    make_community,
    make_user,
)
from openbook_communities.tests.helpers import assert_collaboration_tools

logger = logging.getLogger(__name__)


@pytest.fixture(scope="session")
def client():
    return AsyncClient()


@pytest.fixture(scope="session")
def django_db_setup(django_db_setup, django_db_blocker):
    with django_db_blocker.unblock():
        call_command("loaddata", "openbook_moderation/fixtures/moderation_categories.json")


@pytest.mark.django_db
class TestCollaborationTools:
    def test_can_add_collaboration_tool(self):
        user = make_user()

        community = make_community()
        community.add_member(user)

        add_collaboration_tool_mutation = """
            mutation test($input: AddCollaborationToolInput!) {
                addCollaborationTool(input: $input) {
                    id
                    url
                    title
                    description
                    collectionType
                    domain
                }
            }
            """

        valid_space_id = str(community.id)
        valid_url = "https://holi.social/"
        valid_title = "Project Holi"
        valid_description = "holi is the network where people and organizations come together for the common good"
        valid_collection_type = "COLLABORATION"
        valid_domain = "Holi"

        valid_input = {
            "spaceId": valid_space_id,
            "url": valid_url,
            "title": valid_title,
            "description": valid_description,
            "collectionType": valid_collection_type,
        }

        response = async_to_sync(schema.execute)(
            add_collaboration_tool_mutation,
            context_value=benedict({"request": {"user": user}}),
            variable_values={"input": valid_input},
        )

        assert response.errors is None

        added_collaboration_tool = response.data["addCollaborationTool"]
        assert "id" in added_collaboration_tool
        assert valid_url == added_collaboration_tool["url"]
        assert valid_title == added_collaboration_tool["title"]
        assert valid_description == added_collaboration_tool["description"]
        assert valid_collection_type in added_collaboration_tool["collectionType"]
        assert valid_domain in added_collaboration_tool["domain"]

    def test_can_not_add_collaboration_tool_if_not_logged_in(self):
        community = make_community()
        add_collaboration_tool_mutation = """
            mutation test($input: AddCollaborationToolInput!) {
                addCollaborationTool(input: $input) {
                    id
                }
            }
            """
        valid_space_id = str(community.id)
        valid_url = "https://holi.social/"
        valid_title = "Project Holi"
        valid_description = "holi is the network where people and organizations come together for the common good"
        valid_collection_type = "COLLABORATION"

        valid_input = {
            "spaceId": valid_space_id,
            "url": valid_url,
            "title": valid_title,
            "description": valid_description,
            "collectionType": valid_collection_type,
        }

        response = async_to_sync(schema.execute)(
            add_collaboration_tool_mutation,
            variable_values={"input": valid_input},
            context_value=benedict({"request": {"user": AnonymousUser}}),
        )

        assert_is_unauthorized(response)

    def test_can_not_add_collaboration_tool_if_not_space_member(self):
        user = make_user()
        community = make_community()

        add_collaboration_tool_mutation = """
            mutation test($input: AddCollaborationToolInput!) {
                addCollaborationTool(input: $input) {
                    id
                }
            }
            """

        valid_space_id = str(community.id)
        valid_url = "https://holi.social/"
        valid_title = "Project Holi"
        valid_description = "holi is the network where people and organizations come together for the common good"
        valid_collection_type = "COLLABORATION"

        valid_input = {
            "spaceId": valid_space_id,
            "url": valid_url,
            "title": valid_title,
            "description": valid_description,
            "collectionType": valid_collection_type,
        }

        response = async_to_sync(schema.execute)(
            add_collaboration_tool_mutation,
            variable_values={"input": valid_input},
            context_value=benedict({"request": {"user": user}}),
        )

        assert response.data is None
        assert (
            "You cannot add a collaboration tool to a community you are not a member of"
            in response.errors[0].extensions["errors"]
        )

    def test_can_not_delete_collaboration_tool_if_not_logged_in(self):
        collaboration_tool = make_collaboration_tool()

        delete_collaboration_tool_mutation = """
            mutation test($id: UUID!) {
                deleteCollaborationTool(id: $id) {
                    success
                }
            }
            """

        response = async_to_sync(schema.execute)(
            delete_collaboration_tool_mutation,
            variable_values={"id": str(collaboration_tool.id)},
            context_value=benedict({"request": {"user": AnonymousUser}}),
        )

        assert_is_unauthorized(response)

    def test_can_not_delete_collaboration_tool_if_not_space_member(self):
        collaboration_tool = make_collaboration_tool()
        user = make_user()

        delete_collaboration_tool_mutation = """
            mutation test($id: UUID!) {
                deleteCollaborationTool(id: $id) {
                    success
                }
            }
            """

        response = async_to_sync(schema.execute)(
            delete_collaboration_tool_mutation,
            variable_values={"id": str(collaboration_tool.id)},
            context_value=benedict({"request": {"user": user}}),
        )

        assert response.data is None
        assert (
            "You cannot delete a collaboration tool in a community you are not a member of"
            in response.errors[0].extensions["errors"]
        )

    def test_can_delete_collaboration_tool_if_admin(self):
        user = make_user()
        community = make_community(creator=user)

        collaboration_tool = make_collaboration_tool(community=community)

        delete_collaboration_tool_mutation = """
            mutation test($id: UUID!) {
                deleteCollaborationTool(id: $id) {
                    success
                }
            }
            """

        response = async_to_sync(schema.execute)(
            delete_collaboration_tool_mutation,
            variable_values={"id": str(collaboration_tool.id)},
            context_value=benedict({"request": {"user": user}}),
        )

        assert response.data["deleteCollaborationTool"]["success"] is True
        assert response.errors is None

    def test_can_delete_collaboration_tool_if_space_member(self):
        user = make_user()
        community = make_community()

        community.add_member(user)

        collaboration_tool = make_collaboration_tool(community=community)

        delete_collaboration_tool_mutation = """
            mutation test($id: UUID!) {
                deleteCollaborationTool(id: $id) {
                    success
                }
            }
            """

        response = async_to_sync(schema.execute)(
            delete_collaboration_tool_mutation,
            variable_values={"id": str(collaboration_tool.id)},
            context_value=benedict({"request": {"user": user}}),
        )

        assert response.data["deleteCollaborationTool"]["success"] is True
        assert response.errors is None

    def test_validates_collaboration_tool_before_update(self):
        user = make_user()
        community = make_community(creator=user)

        collaboration_tool = make_collaboration_tool(community=community)

        update_collaboration_tool_mutation = """
            mutation test($input: UpdateCollaborationToolInput!) {
                updateCollaborationTool(input: $input) {
                    id
                }
            }
            """
        base_input = {"id": str(collaboration_tool.id)}
        invalid_uuid = str(uuid4())

        expectedErrors = [
            {"field": "id", "value": None, "expected_error": "Expected non-nullable type"},
            {
                "field": "id",
                "value": invalid_uuid,
                "expected_error": "No collaboration tool with the provided id exists",
            },
            {"field": "url", "value": None, "expected_code": "null"},
            {"field": "url", "value": "", "expected_code": "blank"},
            {"field": "url", "value": "holi.social", "expected_code": "invalid"},
            {"field": "title", "value": None, "expected_code": "null"},
            {"field": "title", "value": "", "expected_code": "blank"},
            {"field": "title", "value": "c", "expected_code": "min_length"},
            {"field": "title", "value": "c" * 61, "expected_code": "max_length"},
            {"field": "description", "value": "c", "expected_code": "min_length"},
            {"field": "description", "value": "c" * 101, "expected_code": "max_length"},
            {"field": "collectionType", "value": None, "expected_code": "null"},
        ]

        for testCase in expectedErrors:
            response = async_to_sync(schema.execute)(
                update_collaboration_tool_mutation,
                context_value=benedict({"request": {"user": user}}),
                variable_values={
                    "input": base_input | {testCase["field"]: testCase["value"]},
                },
            )

            if "expected_code" in testCase:
                field_errors = json.loads(response.errors[0].extensions["errors"])
                assert testCase["expected_code"] == field_errors[testCase["field"]][0]["code"]
            else:
                assert testCase["expected_error"] in str(response.errors[0].message)
            assert (response.data["updateSpace"] if response.data else response.data) is None

    def test_can_not_update_collaboration_tool_without_passing_id(self):
        user = make_user()
        update_collaboration_tool_mutation = """
            mutation test($input: UpdateCollaborationToolInput!) {
                updateCollaborationTool(input: $input) {
                    id
                }
            }
            """

        response = async_to_sync(schema.execute)(
            update_collaboration_tool_mutation,
            context_value=benedict({"request": {"user": user}}),
            variable_values={"input": {"url": "https://holi.social/"}},
        )

        assert response.data is None
        assert "Field 'id' of required type 'UUID!' was not provided" in response.errors[0].message

    def test_can_not_update_collaboration_tool_if_not_space_member(self):
        user = make_user()
        collaboration_tool = make_collaboration_tool()

        update_collaboration_tool_mutation = """
            mutation test($input: UpdateCollaborationToolInput!) {
                updateCollaborationTool(input: $input) {
                    id
                }
            }
            """

        input = {"id": str(collaboration_tool.id), "url": "https://holi.social/"}

        response = async_to_sync(schema.execute)(
            update_collaboration_tool_mutation,
            context_value=benedict({"request": {"user": user}}),
            variable_values={"input": input},
        )

        assert response.data is None
        assert "You cannot update a collaboration tool in a community you are not a member of" in str(
            response.errors[0].extensions["errors"]
        )

    def test_can_not_update_collaboration_tool_if_not_logged_in(self):
        collaboration_tool = make_collaboration_tool()

        update_collaboration_tool_mutation = """
            mutation test($input: UpdateCollaborationToolInput!) {
                updateCollaborationTool(input: $input) {
                    id
                }
            }
            """

        input = {"id": str(collaboration_tool.id), "url": "https://holi.social/"}

        response = async_to_sync(schema.execute)(
            update_collaboration_tool_mutation,
            context_value=benedict({"request": {"user": AnonymousUser}}),
            variable_values={"input": input},
        )

        assert_is_unauthorized(response)

    def test_can_update_collaboration_tool(self):
        user = make_user()
        community = make_community(creator=user)

        collaboration_tool = make_collaboration_tool(community=community)

        update_collaboration_tool_mutation = """
            mutation test($input: UpdateCollaborationToolInput!) {
                updateCollaborationTool(input: $input) {
                    id
                }
            }
            """
        base_input = {"id": str(collaboration_tool.id)}

        valid_url = "https://holi.social/"
        valid_title = "Project Holi"
        valid_description = "holi is the network where people and organizations come together for the common good"
        valid_collection_type = "COLLABORATION"

        valid_inputs = [
            {"url": valid_url},
            {"title": valid_title},
            {"description": valid_description},
            {"collectionType": valid_collection_type},
            {
                "url": valid_url,
                "title": valid_title,
                "description": valid_description,
                "collectionType": valid_collection_type,
            },
        ]

        for input in valid_inputs:
            response = async_to_sync(schema.execute)(
                update_collaboration_tool_mutation,
                context_value=benedict({"request": {"user": user}}),
                variable_values={"input": base_input | input},
            )

            assert str(collaboration_tool.id) == response.data["updateCollaborationTool"]["id"]
            assert response.errors is None

    def test_updated_collaboration_tool_has_new_values(self):
        user = make_user()
        community = make_community(creator=user)

        collaboration_tool = make_collaboration_tool(community=community)

        update_collaboration_tool_mutation = """
            mutation test($input: UpdateCollaborationToolInput!) {
                updateCollaborationTool(input: $input) {
                    id
                    url
                    title
                    description
                    collectionType
                }
            }
            """
        id = str(collaboration_tool.id)
        new_url = "https://holi.social/"
        new_title = "Project Holi"
        new_description = "holi is the network where people and organizations come together for the common good"
        new_collection_type = "COLLABORATION"

        input = {
            "id": id,
            "url": new_url,
            "title": new_title,
            "description": new_description,
            "collectionType": new_collection_type,
        }

        response = async_to_sync(schema.execute)(
            update_collaboration_tool_mutation,
            context_value=benedict({"request": {"user": user}}),
            variable_values={"input": input},
        )

        assert response.errors is None

        updated_collaboration_tool = response.data["updateCollaborationTool"]

        assert id == updated_collaboration_tool["id"]
        assert new_url == updated_collaboration_tool["url"]
        assert new_title == updated_collaboration_tool["title"]
        assert new_description == updated_collaboration_tool["description"]
        assert new_collection_type == updated_collaboration_tool["collectionType"]

    def test_collaboration_tools_only_visible_to_members(self):
        user = make_user()
        member = make_user()
        community = make_community()
        community.add_member(member)
        collaboration_tool = make_collaboration_tool(community=community)

        assert_collaboration_tools(community.id, AnonymousUser, [])
        assert_collaboration_tools(community.id, user, [])
        assert_collaboration_tools(community.id, member, [{"id": str(collaboration_tool.id)}])

    def test_can_not_invite_to_space_by_email_if_not_logged_in(self):
        community = make_community()

        invite_to_space_by_email_mutation = """
            mutation InviteToSpaceByEmail($email: String!, $spaceId: UUID!) {
                inviteToSpaceByEmail(email: $email, spaceId: $spaceId) {
                    success
                }
            }
            """

        valid_input = {
            "email": "test@test.com",
            "spaceId": str(community.id),
        }

        response = async_to_sync(schema.execute)(
            invite_to_space_by_email_mutation,
            variable_values=valid_input,
            context_value=benedict({"request": {"user": AnonymousUser, "META": {"HTTP_ACCEPT_LANGUAGE": "de"}}}),
        )

        assert_is_unauthorized(response)

    def test_can_not_add_collaboration_tool_missing_required_fields(self):
        user = make_user()

        community = make_community()
        community.add_member(user)

        add_collaboration_tool_mutation = """
            mutation test($input: AddCollaborationToolInput!) {
                addCollaborationTool(input: $input) {
                    id
                }
            }
            """

        valid_space_id = str(community.id)
        valid_url = "https://holi.social/"
        valid_title = "Project Holi"
        valid_collection_type = "COLLABORATION"

        expectedErrors = [
            {
                "input": {"url": valid_url, "title": valid_title, "spaceId": valid_space_id},
                "expected_error": "was not provided",
            },
            {
                "input": {"url": valid_url, "spaceId": valid_space_id, "collectionType": valid_collection_type},
                "expected_error": "was not provided",
            },
            {
                "input": {"title": valid_title, "spaceId": valid_space_id, "collectionType": valid_collection_type},
                "expected_error": "was not provided",
            },
        ]

        for testCase in expectedErrors:
            response = async_to_sync(schema.execute)(
                add_collaboration_tool_mutation,
                context_value=benedict({"request": {"user": user}}),
                variable_values={"input": testCase["input"]},
            )

            assert testCase["expected_error"] in str(response.errors[0].message)
            assert (response.data["addCollaborationTool"] if response.data else response.data) is None

    def test_validates_collaboration_tool_before_creation(self):
        user = make_user()

        community = make_community()
        community.add_member(user)

        add_collaboration_tool_mutation = """
            mutation test($input: AddCollaborationToolInput!) {
                addCollaborationTool(input: $input) {
                    id
                }
            }
            """

        valid_space_id = str(community.id)
        valid_url = "https://holi.social/"
        valid_title = "Project Holi"
        valid_description = "holi is the network where people and organizations come together for the common good"
        valid_collection_type = "COLLABORATION"

        valid_input = {
            "spaceId": valid_space_id,
            "url": valid_url,
            "title": valid_title,
            "description": valid_description,
            "collectionType": valid_collection_type,
        }

        expectedErrors = [
            {"field": "url", "value": None, "expected_error": "Expected non-nullable type"},
            {"field": "url", "value": "", "expected_code": "blank"},
            {"field": "url", "value": "holi.social", "expected_code": "invalid"},
            {"field": "title", "value": None, "expected_error": "Expected non-nullable type"},
            {"field": "title", "value": "", "expected_code": "blank"},
            {"field": "title", "value": "c", "expected_code": "min_length"},
            {"field": "title", "value": "c" * 61, "expected_code": "max_length"},
            {"field": "description", "value": "c", "expected_code": "min_length"},
            {"field": "description", "value": "c" * 101, "expected_code": "max_length"},
            {"field": "collectionType", "value": None, "expected_error": "Expected non-nullable type"},
        ]

        for testCase in expectedErrors:
            response = async_to_sync(schema.execute)(
                add_collaboration_tool_mutation,
                context_value=benedict({"request": {"user": user}}),
                variable_values={"input": valid_input | {testCase["field"]: testCase["value"]}},
            )

            if "expected_code" in testCase:
                field_errors = json.loads(response.errors[0].extensions["errors"])
                assert testCase["expected_code"] == field_errors[testCase["field"]][0]["code"]
            else:
                assert testCase["expected_error"] in str(response.errors[0].message)
            assert (response.data["addCollaborationTool"] if response.data else response.data) is None
