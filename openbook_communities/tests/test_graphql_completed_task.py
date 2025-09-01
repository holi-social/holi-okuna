import logging
from uuid import uuid4

import pytest
from asgiref.sync import async_to_sync
from benedict import benedict
from django.contrib.auth.models import AnonymousUser
from django.core.management import call_command
from django.test import AsyncClient
from unittest.mock import patch

from openbook.graphql_schema import schema
from openbook_common.tests.helpers import (
    assert_is_unauthorized,
    make_community,
    make_community_task,
    make_user,
)
from openbook_communities.models.completed_task import CompletedTask
from openbook_communities.models import Community as CommunityModel
from openbook_communities.signals import TaskCompletedEvent

logger = logging.getLogger(__name__)


@pytest.fixture(scope="session")
def client():
    return AsyncClient()


@pytest.fixture(scope="session")
def django_db_setup(django_db_setup, django_db_blocker):
    with django_db_blocker.unblock():
        call_command("loaddata", "openbook_moderation/fixtures/moderation_categories.json")


@pytest.mark.django_db
class TestCompleteReadyToGoTask:
    def test_can_complete_ready_to_go_task(self):
        user = make_user()
        community = make_community()
        community.add_member(user)
        task = make_community_task(community=community, interaction_type="READY")

        complete_task_mutation = """
            mutation CompleteReadyToGoTask($id: UUID!) {
                completeReadyToGoTask(id: $id) {
                    id
                    task {
                        id
                        name
                    }
                    user {
                        id
                        fullName
                    }
                    completedAt
                }
            }
        """

        response = async_to_sync(schema.execute)(
            complete_task_mutation,
            context_value=benedict({"request": {"user": user}}),
            variable_values={"id": str(task.id)},
        )

        assert response.errors is None
        assert response.data is not None

        completed_task = response.data["completeReadyToGoTask"]
        assert "id" in completed_task
        assert completed_task["task"]["id"] == str(task.id)
        assert completed_task["task"]["name"] == task.name
        assert completed_task["user"]["id"] == str(user.id)
        assert completed_task["user"]["fullName"] == user.profile.full_name()
        assert "completedAt" in completed_task

        # Verify the completed task was created in the database
        completed_task_obj = CompletedTask.objects.get(id=completed_task["id"])
        assert completed_task_obj.task == task
        assert completed_task_obj.user == user

    def test_can_not_complete_task_if_not_logged_in(self):
        community = make_community()
        task = make_community_task(community=community)

        complete_task_mutation = """
            mutation CompleteReadyToGoTask($id: UUID!) {
                completeReadyToGoTask(id: $id) {
                    id
                }
            }
        """

        response = async_to_sync(schema.execute)(
            complete_task_mutation,
            context_value=benedict({"request": {"user": AnonymousUser}}),
            variable_values={"id": str(task.id)},
        )

        assert_is_unauthorized(response)

    def test_can_not_complete_task_if_not_space_member(self):
        user = make_user()
        community = make_community()
        task = make_community_task(community=community)

        complete_task_mutation = """
            mutation CompleteReadyToGoTask($id: UUID!) {
                completeReadyToGoTask(id: $id) {
                    id
                }
            }
        """

        response = async_to_sync(schema.execute)(
            complete_task_mutation,
            context_value=benedict({"request": {"user": user}}),
            variable_values={"id": str(task.id)},
        )

        assert response.data is None
        assert len(response.errors) > 0
        # The error should indicate the user cannot access the task

    def test_can_complete_ready_to_go_task_if_space_member(self):
        user = make_user()
        community = make_community()
        community.add_member(user)
        task = make_community_task(community=community, interaction_type="READY")

        complete_task_mutation = """
            mutation CompleteReadyToGoTask($id: UUID!) {
                completeReadyToGoTask(id: $id) {
                    id
                    task {
                        id
                    }
                }
            }
        """

        response = async_to_sync(schema.execute)(
            complete_task_mutation,
            context_value=benedict({"request": {"user": user}}),
            variable_values={"id": str(task.id)},
        )

        assert response.errors is None
        assert response.data is not None
        assert response.data["completeReadyToGoTask"]["id"] is not None

    def test_can_complete_ready_to_go_task_if_space_admin(self):
        user = make_user()
        community = make_community(creator=user)
        task = make_community_task(community=community, interaction_type="READY")

        complete_task_mutation = """
            mutation CompleteReadyToGoTask($id: UUID!) {
                completeReadyToGoTask(id: $id) {
                    id
                    task {
                        id
                    }
                }
            }
        """

        response = async_to_sync(schema.execute)(
            complete_task_mutation,
            context_value=benedict({"request": {"user": user}}),
            variable_values={"id": str(task.id)},
        )

        assert response.errors is None
        assert response.data is not None
        assert response.data["completeReadyToGoTask"]["id"] is not None

    def test_can_not_complete_nonexistent_task(self):
        user = make_user()
        community = make_community()
        community.add_member(user)
        fake_task_id = str(uuid4())

        complete_task_mutation = """
            mutation CompleteReadyToGoTask($id: UUID!) {
                completeReadyToGoTask(id: $id) {
                    id
                }
            }
        """

        response = async_to_sync(schema.execute)(
            complete_task_mutation,
            context_value=benedict({"request": {"user": user}}),
            variable_values={"id": fake_task_id},
        )

        assert response.data is None
        assert len(response.errors) > 0
        # Should get an error about task not existing

    def test_can_complete_task_with_ready_interaction_type(self):
        user = make_user()
        community = make_community()
        community.add_member(user)
        # Create a task with READY interaction type
        task = make_community_task(community=community, interaction_type="READY")

        complete_task_mutation = """
            mutation CompleteReadyToGoTask($id: UUID!) {
                completeReadyToGoTask(id: $id) {
                    id
                    task {
                        id
                        name
                    }
                    user {
                        id
                        fullName
                    }
                }
            }
        """

        response = async_to_sync(schema.execute)(
            complete_task_mutation,
            context_value=benedict({"request": {"user": user}}),
            variable_values={"id": str(task.id)},
        )

        assert response.errors is None
        assert response.data is not None
        completed_task = response.data["completeReadyToGoTask"]
        assert completed_task["id"] is not None
        assert completed_task["task"]["id"] == str(task.id)
        assert completed_task["task"]["name"] == task.name
        assert completed_task["user"]["id"] == str(user.id)
        assert completed_task["user"]["fullName"] == user.profile.full_name()

        # Verify the completed task was created in the database
        completed_task_obj = CompletedTask.objects.get(id=completed_task["id"])
        assert completed_task_obj.task == task
        assert completed_task_obj.user == user

    def test_can_not_complete_task_with_wrong_interaction_type(self):
        user = make_user()
        community = make_community()
        community.add_member(user)
        # Create a task with CHAT interaction type (not READY)
        task = make_community_task(community=community, interaction_type="CHAT")

        complete_task_mutation = """
            mutation CompleteReadyToGoTask($id: UUID!) {
                completeReadyToGoTask(id: $id) {
                    id
                }
            }
        """

        response = async_to_sync(schema.execute)(
            complete_task_mutation,
            context_value=benedict({"request": {"user": user}}),
            variable_values={"id": str(task.id)},
        )

        assert response.data is None
        assert len(response.errors) > 0
        # Should get a FORBIDDEN error about interaction type
        error = response.errors[0]
        assert "Only tasks with 'Ready to Go' interaction type can be completed" in str(error.message)

    def test_error_codes_are_separated(self):
        user = make_user()
        community = make_community()
        community.add_member(user)

        # Test 1: Non-existent task should return NOT_FOUND
        fake_task_id = str(uuid4())
        complete_task_mutation = """
            mutation CompleteReadyToGoTask($id: UUID!) {
                completeReadyToGoTask(id: $id) {
                    id
                }
            }
        """

        response1 = async_to_sync(schema.execute)(
            complete_task_mutation,
            context_value=benedict({"request": {"user": user}}),
            variable_values={"id": fake_task_id},
        )

        assert response1.data is None
        assert len(response1.errors) > 0
        error1 = response1.errors[0]
        assert "Task not found" in str(error1.message)

        # Test 2: Task exists but user has no access should return FORBIDDEN
        # Create a task in a different community where user is not a member
        other_community = make_community()
        task = make_community_task(community=other_community, interaction_type="READY")
        response2 = async_to_sync(schema.execute)(
            complete_task_mutation,
            context_value=benedict({"request": {"user": user}}),
            variable_values={"id": str(task.id)},
        )

        assert response2.data is None
        assert len(response2.errors) > 0
        error2 = response2.errors[0]
        assert "You don't have permission to access this task or it has expired" in str(error2.message)

    def test_can_not_complete_task_with_invalid_uuid(self):
        user = make_user()
        community = make_community()
        community.add_member(user)

        complete_task_mutation = """
            mutation CompleteReadyToGoTask($id: UUID!) {
                completeReadyToGoTask(id: $id) {
                    id
                }
            }
        """

        response = async_to_sync(schema.execute)(
            complete_task_mutation,
            context_value=benedict({"request": {"user": user}}),
            variable_values={"id": "invalid-uuid"},
        )

        assert response.data is None
        assert len(response.errors) > 0
        # Should get a GraphQL validation error for invalid UUID format

    def test_can_not_complete_task_without_id(self):
        user = make_user()
        community = make_community()
        community.add_member(user)

        complete_task_mutation = """
            mutation CompleteReadyToGoTask($id: UUID!) {
                completeReadyToGoTask(id: $id) {
                    id
                }
            }
        """

        response = async_to_sync(schema.execute)(
            complete_task_mutation,
            context_value=benedict({"request": {"user": user}}),
            variable_values={},
        )

        assert response.data is None
        assert len(response.errors) > 0
        # Should get a GraphQL validation error for missing required parameter

    def test_can_complete_multiple_ready_to_go_tasks(self):
        user = make_user()
        community = make_community()
        community.add_member(user)
        task1 = make_community_task(community=community, interaction_type="READY")
        task2 = make_community_task(community=community, interaction_type="READY")

        complete_task_mutation = """
            mutation CompleteReadyToGoTask($id: UUID!) {
                completeReadyToGoTask(id: $id) {
                    id
                    task {
                        id
                    }
                }
            }
        """

        # Complete first task
        response1 = async_to_sync(schema.execute)(
            complete_task_mutation,
            context_value=benedict({"request": {"user": user}}),
            variable_values={"id": str(task1.id)},
        )

        assert response1.errors is None
        completed_task1_id = response1.data["completeReadyToGoTask"]["id"]

        # Complete second task
        response2 = async_to_sync(schema.execute)(
            complete_task_mutation,
            context_value=benedict({"request": {"user": user}}),
            variable_values={"id": str(task2.id)},
        )

        assert response2.errors is None
        completed_task2_id = response2.data["completeReadyToGoTask"]["id"]

        # Verify both completed tasks exist
        assert completed_task1_id != completed_task2_id
        assert CompletedTask.objects.filter(id=completed_task1_id).exists()
        assert CompletedTask.objects.filter(id=completed_task2_id).exists()

    def test_completed_ready_to_go_task_has_correct_timestamp(self):
        user = make_user()
        community = make_community()
        community.add_member(user)
        task = make_community_task(community=community, interaction_type="READY")

        complete_task_mutation = """
            mutation CompleteReadyToGoTask($id: UUID!) {
                completeReadyToGoTask(id: $id) {
                    id
                    completedAt
                }
            }
        """

        response = async_to_sync(schema.execute)(
            complete_task_mutation,
            context_value=benedict({"request": {"user": user}}),
            variable_values={"id": str(task.id)},
        )

        assert response.errors is None
        completed_task = response.data["completeReadyToGoTask"]
        assert "completedAt" in completed_task
        assert completed_task["completedAt"] is not None

    def test_can_complete_ready_to_go_task_in_private_community(self):
        user = make_user()
        community = make_community(type=CommunityModel.COMMUNITY_TYPE_PRIVATE)
        community.add_member(user)
        task = make_community_task(community=community, interaction_type="READY")

        complete_task_mutation = """
            mutation CompleteReadyToGoTask($id: UUID!) {
                completeReadyToGoTask(id: $id) {
                    id
                    task {
                        id
                    }
                }
            }
        """

        response = async_to_sync(schema.execute)(
            complete_task_mutation,
            context_value=benedict({"request": {"user": user}}),
            variable_values={"id": str(task.id)},
        )

        assert response.errors is None
        assert response.data is not None
        assert response.data["completeReadyToGoTask"]["id"] is not None

        # Verify the completed task was created in the database
        completed_task_obj = CompletedTask.objects.get(id=response.data["completeReadyToGoTask"]["id"])
        assert completed_task_obj.task == task
        assert completed_task_obj.user == user

    def test_can_not_complete_ready_to_go_task_in_private_community_if_not_member(self):
        user = make_user()
        community = make_community(type=CommunityModel.COMMUNITY_TYPE_PRIVATE)
        task = make_community_task(community=community)

        complete_task_mutation = """
            mutation CompleteReadyToGoTask($id: UUID!) {
                completeReadyToGoTask(id: $id) {
                    id
                }
            }
        """

        response = async_to_sync(schema.execute)(
            complete_task_mutation,
            context_value=benedict({"request": {"user": user}}),
            variable_values={"id": str(task.id)},
        )

        assert response.data is None
        assert len(response.errors) > 0
        # Should get an error about not being able to access the task

    def test_completed_ready_to_go_task_returns_correct_user_information(self):
        user = make_user()
        community = make_community()
        community.add_member(user)
        task = make_community_task(community=community, interaction_type="READY")

        complete_task_mutation = """
            mutation CompleteReadyToGoTask($id: UUID!) {
                completeReadyToGoTask(id: $id) {
                    id
                    user {
                        id
                        fullName
                        lastName
                    }
                }
            }
        """

        response = async_to_sync(schema.execute)(
            complete_task_mutation,
            context_value=benedict({"request": {"user": user}}),
            variable_values={"id": str(task.id)},
        )

        assert response.errors is None
        completed_task = response.data["completeReadyToGoTask"]
        assert completed_task["user"]["id"] == str(user.id)
        assert completed_task["user"]["fullName"] == user.profile.full_name()
        assert completed_task["user"]["lastName"] == user.last_name

    def test_completed_ready_to_go_task_returns_correct_task_information(self):
        user = make_user()
        community = make_community()
        community.add_member(user)
        task = make_community_task(
            community=community, name="Test Task", description="Test Description", interaction_type="READY"
        )

        complete_task_mutation = """
            mutation CompleteReadyToGoTask($id: UUID!) {
                completeReadyToGoTask(id: $id) {
                    id
                    task {
                        id
                        name
                        description
                    }
                }
            }
        """

        response = async_to_sync(schema.execute)(
            complete_task_mutation,
            context_value=benedict({"request": {"user": user}}),
            variable_values={"id": str(task.id)},
        )

        assert response.errors is None
        completed_task = response.data["completeReadyToGoTask"]
        assert completed_task["task"]["id"] == str(task.id)
        assert completed_task["task"]["name"] == task.name
        assert completed_task["task"]["description"] == task.description

    @patch("openbook_communities.signals.publish_to_okuna_topic")
    def test_complete_ready_to_go_task_publishes_signal(self, mock_publish):
        user = make_user()
        community = make_community()
        # Make user a member of the community so they can access the task
        community.add_member(user)
        task = make_community_task(community=community, interaction_type="READY")

        complete_task_mutation = """
            mutation CompleteReadyToGoTask($id: UUID!) {
                completeReadyToGoTask(id: $id) {
                    id
                    task {
                        id
                        name
                    }
                    user {
                        id
                        fullName
                    }
                }
            }
        """

        variables = {"id": str(task.id)}

        result = async_to_sync(schema.execute)(
            complete_task_mutation,
            variable_values=variables,
            context_value=benedict({"request": {"user": user}}),
        )

        # Verify the mutation succeeded
        assert not result.errors
        completed_task_data = result.data["completeReadyToGoTask"]
        assert completed_task_data["task"]["id"] == str(task.id)

        # Verify the signal was published
        mock_publish.assert_called_once()
        call_args = mock_publish.call_args[0][0]
        assert isinstance(call_args, TaskCompletedEvent)
        assert call_args.completed_task.task.id == task.id
        assert call_args.completed_task.user.id == user.id
        assert call_args.event_type == "TaskCompleted"
        assert call_args.event_version == "1.0.0"
        assert call_args.additional_attributes["userId"] == user.username

    def test_task_completed_event_data(self):
        user = make_user()
        community = make_community()
        task = make_community_task(community=community)

        # Create a completed task directly to test the event
        completed_task = CompletedTask.objects.create(task=task, user=user)

        event = TaskCompletedEvent(completed_task)

        assert event.event_type == "TaskCompleted"
        assert event.event_version == "1.0.0"
        assert event.additional_attributes["userId"] == user.username
        assert event.log_str() == f"TaskCompleted(completed_task_id={completed_task.id})"

    @patch("openbook_communities.signals.publish_to_okuna_topic")
    def test_signal_handler_only_publishes_on_creation(self, mock_publish):
        user = make_user()
        community = make_community()
        task = make_community_task(community=community)

        # Create completed task (should trigger signal)
        completed_task = CompletedTask.objects.create(task=task, user=user)
        mock_publish.assert_called_once()
        mock_publish.reset_mock()

        # Update completed task (should not trigger signal)
        completed_task.save()
        mock_publish.assert_not_called()

    @patch("openbook_communities.signals.publish_to_okuna_topic")
    def test_signal_handler_ignores_wrong_model(self, mock_publish):
        community = make_community()
        task = make_community_task(community=community)

        # The signal is only connected to CompletedTask models, so creating a Task
        # should not trigger the signal
        task.save()  # This should not trigger the signal

        # Should not publish anything for Task model
        mock_publish.assert_not_called()

    def test_can_complete_public_ready_to_go_task_if_not_space_member(self):
        user = make_user()
        community = make_community()
        task = make_community_task(community=community, visibility="PUBLIC", interaction_type="READY")

        complete_task_mutation = """
            mutation CompleteReadyToGoTask($id: UUID!) {
                completeReadyToGoTask(id: $id) {
                    id
                    task {
                        id
                        name
                    }
                    user {
                        id
                        fullName
                    }
                }
            }
        """

        response = async_to_sync(schema.execute)(
            complete_task_mutation,
            context_value=benedict({"request": {"user": user}}),
            variable_values={"id": str(task.id)},
        )

        assert response.errors is None
        assert response.data is not None
        assert response.data["completeReadyToGoTask"]["id"] is not None

        # Verify the completed task was created in the database
        completed_task_obj = CompletedTask.objects.get(id=response.data["completeReadyToGoTask"]["id"])
        assert completed_task_obj.task == task
        assert completed_task_obj.user == user

    def test_can_complete_same_task_multiple_times(self):
        user = make_user()
        community = make_community()
        community.add_member(user)
        task = make_community_task(community=community, interaction_type="READY")

        complete_task_mutation = """
            mutation CompleteReadyToGoTask($id: UUID!) {
                completeReadyToGoTask(id: $id) {
                    id
                    task {
                        id
                        name
                    }
                    user {
                        id
                        fullName
                    }
                }
            }
        """

        # First completion should succeed
        response1 = async_to_sync(schema.execute)(
            complete_task_mutation,
            context_value=benedict({"request": {"user": user}}),
            variable_values={"id": str(task.id)},
        )

        assert response1.errors is None
        assert response1.data is not None
        first_completion_id = response1.data["completeReadyToGoTask"]["id"]

        # Second completion of the same task should also succeed
        response2 = async_to_sync(schema.execute)(
            complete_task_mutation,
            context_value=benedict({"request": {"user": user}}),
            variable_values={"id": str(task.id)},
        )

        assert response2.errors is None
        assert response2.data is not None
        second_completion_id = response2.data["completeReadyToGoTask"]["id"]

        # Verify both completed tasks exist in the database
        completed_tasks = CompletedTask.objects.filter(task=task, user=user)
        assert completed_tasks.count() == 2

        # Verify the IDs are different (two separate completions)
        assert first_completion_id != second_completion_id

        # Verify both completed tasks reference the same task and user
        first_completion = CompletedTask.objects.get(id=first_completion_id)
        second_completion = CompletedTask.objects.get(id=second_completion_id)

        assert first_completion.task == task
        assert first_completion.user == user
        assert second_completion.task == task
        assert second_completion.user == user
