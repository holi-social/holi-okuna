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
    make_community,
    make_external_link,
    make_user,
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
class TestExternalLinks:
    def test_can_not_add_external_link_missing_required_fields(self):
        user = make_user()
        community = make_community(creator=user)

        add_external_link_mutation = """
            mutation test($input: AddExternalLinkInput!) {
                addExternalLink(input: $input) {
                    id
                }
            }
            """

        valid_space_id = str(community.id)
        valid_url = "https://www.instagram.com/"
        valid_type = "INSTAGRAM"
        valid_name = "Instagram"

        expectedErrors = [
            {
                "input": {"url": valid_url, "spaceId": valid_space_id, "type": valid_type},
                "expected_error": "was not provided",
            },
            {
                "input": {"url": valid_url, "type": valid_type, "name": valid_name},
                "expected_error": "was not provided",
            },
            {
                "input": {"spaceId": valid_space_id, "type": valid_type, "name": valid_name},
                "expected_error": "was not provided",
            },
            {
                "input": {"spaceId": valid_space_id, "url": valid_url, "name": valid_name},
                "expected_error": "was not provided",
            },
        ]

        for testCase in expectedErrors:
            response = async_to_sync(schema.execute)(
                add_external_link_mutation,
                context_value=benedict({"request": {"user": user}}),
                variable_values={"input": testCase["input"]},
            )

            assert testCase["expected_error"] in str(response.errors[0].message)
            assert (response.data["addExternalLink"] if response.data else response.data) is None

    def test_validates_external_link_before_creation(self):
        user = make_user()
        community = make_community(creator=user)

        add_external_link_mutation = """
            mutation test($input: AddExternalLinkInput!) {
                addExternalLink(input: $input) {
                    id
                }
            }
            """

        valid_space_id = str(community.id)
        valid_url = "https://www.instagram.com/"
        valid_type = "INSTAGRAM"
        valid_name = "Instagram"

        valid_input = {
            "spaceId": valid_space_id,
            "url": valid_url,
            "type": valid_type,
            "name": valid_name,
        }

        expectedErrors = [
            {"field": "url", "value": None, "expected_error": "Expected non-nullable type"},
            {"field": "url", "value": "", "expected_code": "blank"},
            {"field": "url", "value": "holi.social", "expected_code": "invalid"},
            {"field": "type", "value": None, "expected_error": "Expected non-nullable type"},
            {"field": "name", "value": None, "expected_error": "Expected non-nullable type"},
        ]

        for testCase in expectedErrors:
            response = async_to_sync(schema.execute)(
                add_external_link_mutation,
                context_value=benedict({"request": {"user": user}}),
                variable_values={"input": valid_input | {testCase["field"]: testCase["value"]}},
            )

            if "expected_code" in testCase:
                field_errors = json.loads(response.errors[0].extensions["errors"])
                assert testCase["expected_code"] == field_errors[testCase["field"]][0]["code"], (
                    f"{str(response.errors[0].extensions)} does not contain code: {testCase['expected_code']} from testCase: {testCase}"
                )
            else:
                assert testCase["expected_error"] in str(response.errors[0].message)
            assert (response.data["addExternalLink"] if response.data else response.data) is None

    def test_can_add_external_link(self):
        user = make_user()
        community = make_community(creator=user)

        add_external_link_mutation = """
            mutation test($input: AddExternalLinkInput!) {
                addExternalLink(input: $input) {
                    id
                    url
                    type
                    name
                }
            }
            """

        valid_space_id = str(community.id)
        valid_url = "https://www.instagram.com/"
        valid_type = "INSTAGRAM"
        valid_name = "Instagram"

        valid_input = {
            "spaceId": valid_space_id,
            "url": valid_url,
            "type": valid_type,
            "name": valid_name,
        }

        response = async_to_sync(schema.execute)(
            add_external_link_mutation,
            context_value=benedict({"request": {"user": user}}),
            variable_values={"input": valid_input},
        )

        assert response.errors is None

        added_external_link = response.data["addExternalLink"]
        assert "id" in added_external_link
        assert valid_url == added_external_link["url"]
        assert valid_type in added_external_link["type"]
        assert valid_name == added_external_link["name"]

    def test_can_not_add_external_link_if_not_logged_in(self):
        community = make_community()
        add_external_link_mutation = """
            mutation test($input: AddExternalLinkInput!) {
                addExternalLink(input: $input) {
                    id
                }
            }
            """
        valid_space_id = str(community.id)
        valid_url = "https://www.instagram.com/"
        valid_type = "INSTAGRAM"
        valid_name = "Instagram"

        valid_input = {
            "spaceId": valid_space_id,
            "url": valid_url,
            "type": valid_type,
            "name": valid_name,
        }

        response = async_to_sync(schema.execute)(
            add_external_link_mutation,
            variable_values={"input": valid_input},
            context_value=benedict({"request": {"user": AnonymousUser}}),
        )

        assert_is_unauthorized(response)

    def test_can_not_add_external_link_if_not_space_admin(self):
        user = make_user()

        community = make_community()
        community.add_member(user)

        add_external_link_mutation = """
            mutation test($input: AddExternalLinkInput!) {
                addExternalLink(input: $input) {
                    id
                }
            }
            """

        valid_space_id = str(community.id)
        valid_url = "https://www.instagram.com/"
        valid_type = "INSTAGRAM"
        valid_name = "Instagram"

        valid_input = {
            "spaceId": valid_space_id,
            "url": valid_url,
            "type": valid_type,
            "name": valid_name,
        }

        response = async_to_sync(schema.execute)(
            add_external_link_mutation,
            variable_values={"input": valid_input},
            context_value=benedict({"request": {"user": user}}),
        )

        assert response.data is None
        assert (
            "You cannot add an external link to a community that you do not administrate"
            in response.errors[0].extensions["errors"]
        )

    def test_can_not_delete_external_link_if_not_logged_in(self):
        external_link = make_external_link()

        delete_external_link_mutation = """
            mutation test($id: UUID!) {
                deleteExternalLink(id: $id) {
                    success
                }
            }
            """

        response = async_to_sync(schema.execute)(
            delete_external_link_mutation,
            variable_values={"id": str(external_link.id)},
            context_value=benedict({"request": {"user": AnonymousUser}}),
        )

        assert_is_unauthorized(response)

    def test_can_not_delete_external_link_if_not_space_admin(self):
        user = make_user()

        community = make_community()
        community.add_member(user)

        external_link = make_external_link(community=community)

        delete_external_link_mutation = """
            mutation test($id: UUID!) {
                deleteExternalLink(id: $id) {
                    success
                }
            }
            """

        response = async_to_sync(schema.execute)(
            delete_external_link_mutation,
            variable_values={"id": str(external_link.id)},
            context_value=benedict({"request": {"user": user}}),
        )

        assert response.data is None
        assert (
            "You cannot delete an external link in a community that you do not administrate"
            in response.errors[0].extensions["errors"]
        )

    def test_can_delete_external_link_if_admin(self):
        user = make_user()
        community = make_community(creator=user)

        external_link = make_external_link(community=community)

        delete_external_link_mutation = """
            mutation test($id: UUID!) {
                deleteExternalLink(id: $id) {
                    success
                }
            }
            """

        response = async_to_sync(schema.execute)(
            delete_external_link_mutation,
            variable_values={"id": str(external_link.id)},
            context_value=benedict({"request": {"user": user}}),
        )

        assert response.data["deleteExternalLink"]["success"] is True
        assert response.errors is None

    def test_validates_external_link_before_update(self):
        user = make_user()
        community = make_community(creator=user)

        external_link = make_external_link(community=community)

        update_external_link_mutation = """
            mutation test($input: UpdateExternalLinkInput!) {
                updateExternalLink(input: $input) {
                    id
                }
            }
            """
        base_input = {"id": str(external_link.id)}
        invalid_uuid = str(uuid4())

        expectedErrors = [
            {"field": "id", "value": None, "expected_error": "Expected non-nullable type"},
            {
                "field": "id",
                "value": invalid_uuid,
                "expected_error": "No external link with the provided id exists.",
            },
            {"field": "url", "value": None, "expected_code": "null"},
            {"field": "url", "value": "", "expected_code": "blank"},
            {"field": "url", "value": "holi.social", "expected_code": "invalid"},
            {"field": "type", "value": None, "expected_code": "null"},
            {"field": "name", "value": None, "expected_code": "null"},
        ]

        for testCase in expectedErrors:
            response = async_to_sync(schema.execute)(
                update_external_link_mutation,
                context_value=benedict({"request": {"user": user}}),
                variable_values={
                    "input": base_input | {testCase["field"]: testCase["value"]},
                },
            )

            if "expected_code" in testCase:
                field_errors = json.loads(response.errors[0].extensions["errors"])
                assert testCase["expected_code"] == field_errors[testCase["field"]][0]["code"], (
                    f"{str(response.errors[0].extensions)} does not contain code: {testCase['expected_code']} from testCase: {testCase}"
                )
            else:
                assert testCase["expected_error"] in str(response.errors[0].message)
            assert (response.data["updateExternalLink"] if response.data else response.data) is None

    def test_can_not_update_external_link_without_passing_id(self):
        user = make_user()
        update_external_link_mutation = """
            mutation test($input: UpdateExternalLinkInput!) {
                updateExternalLink(input: $input) {
                    id
                }
            }
            """

        response = async_to_sync(schema.execute)(
            update_external_link_mutation,
            context_value=benedict({"request": {"user": user}}),
            variable_values={"input": {"url": "https://www.instagram.com/", "type": "INSTAGRAM"}},
        )

        assert response.data is None
        assert "Field 'id' of required type 'UUID!' was not provided" in response.errors[0].message

    def test_can_not_update_external_link_if_not_space_admin(self):
        user = make_user()

        community = make_community()
        community.add_member(user)

        external_link = make_external_link(community=community)

        update_external_link_mutation = """
            mutation test($input: UpdateExternalLinkInput!) {
                updateExternalLink(input: $input) {
                    id
                }
            }
            """

        input = {
            "id": str(external_link.id),
            "url": "https://www.instagram.com/",
            "type": "INSTAGRAM",
            "name": "Instagram",
        }

        response = async_to_sync(schema.execute)(
            update_external_link_mutation,
            context_value=benedict({"request": {"user": user}}),
            variable_values={"input": input},
        )

        assert response.data is None
        assert "You cannot update an external link in a community that you do not administrate" in str(
            response.errors[0].extensions["errors"]
        )

    def test_can_not_update_external_link_if_not_logged_in(self):
        external_link = make_external_link()

        update_external_link_mutation = """
            mutation test($input: UpdateExternalLinkInput!) {
                updateExternalLink(input: $input) {
                    id
                }
            }
            """

        input = {
            "id": str(external_link.id),
            "url": "https://www.instagram.com/",
            "type": "INSTAGRAM",
            "name": "Instagram",
        }

        response = async_to_sync(schema.execute)(
            update_external_link_mutation,
            context_value=benedict({"request": {"user": AnonymousUser}}),
            variable_values={"input": input},
        )

        assert_is_unauthorized(response)

    def test_can_update_external_link(self):
        user = make_user()
        community = make_community(creator=user)

        external_link = make_external_link(community=community)

        update_external_link_mutation = """
            mutation test($input: UpdateExternalLinkInput!) {
                updateExternalLink(input: $input) {
                    id
                }
            }
            """

        input = {
            "id": str(external_link.id),
            "url": "https://www.instagram.com/",
            "type": "INSTAGRAM",
            "name": "Instagram",
        }

        response = async_to_sync(schema.execute)(
            update_external_link_mutation,
            context_value=benedict({"request": {"user": user}}),
            variable_values={"input": input},
        )

        assert str(external_link.id) == response.data["updateExternalLink"]["id"]
        assert response.errors is None

    def test_updated_external_link_has_new_values(self):
        user = make_user()
        community = make_community(creator=user)

        external_link = make_external_link(community=community)

        update_external_link_mutation = """
            mutation test($input: UpdateExternalLinkInput!) {
                updateExternalLink(input: $input) {
                    id
                    url
                    type
                    name
                }
            }
            """
        id = str(external_link.id)
        new_url = "https://www.instagram.com/"
        new_type = "INSTAGRAM"
        new_name = "Instagram"

        input = {
            "id": id,
            "url": new_url,
            "type": new_type,
            "name": new_name,
        }

        response = async_to_sync(schema.execute)(
            update_external_link_mutation,
            context_value=benedict({"request": {"user": user}}),
            variable_values={"input": input},
        )

        assert response.errors is None

        updated_external_link = response.data["updateExternalLink"]

        assert id == updated_external_link["id"]
        assert new_url == updated_external_link["url"]
        assert new_type == updated_external_link["type"]
        assert new_name == updated_external_link["name"]
