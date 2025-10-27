import logging
from unittest import mock
from unittest.mock import call

import pytest
from asgiref.sync import async_to_sync
from benedict import benedict
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase

from openbook.graphql_schema import schema
from openbook_common.tracking import initialize_tracking, PostHogConfig, TrackingEvent
from openbook_common.tests.helpers import (
    make_user,
    make_community as make_space,
    make_community_task,
    simple_jpeg_bytes,
    make_topics_v2,
    make_skill_v2,
)
from openbook_communities.tests.helpers import mutate_update_space_user_connection_data
from openbook_communities.models import SpaceUserConnectionType
from openbook_communities.enums import UpdateConnectionAction


logger = logging.getLogger(__name__)


def consenting_user():
    return make_user(tracking_consent_analytics=True, tracking_consent_personalization=True)


def invite_to_space(space, invitor, invitee):
    return mutate_update_space_user_connection_data(
        auth_user=invitor,
        space_id=space.id,
        connection_type=SpaceUserConnectionType.MEMBERSHIP_INVITEE,
        connect_action=UpdateConnectionAction.CONNECT,
        message="bla",
        user_id=invitee.id,
    )


def accept_space_invitation(space, invitee):
    return mutate_update_space_user_connection_data(
        auth_user=invitee,
        space_id=space.id,
        connection_type=SpaceUserConnectionType.MEMBERSHIP_INVITEE,
        connect_action=UpdateConnectionAction.CONNECT,
        message="bla",
    )


def reject_space_invitation(space, invitee):
    return mutate_update_space_user_connection_data(
        auth_user=invitee,
        space_id=space.id,
        connection_type=SpaceUserConnectionType.MEMBERSHIP_INVITEE,
        connect_action=UpdateConnectionAction.DISCONNECT,
        message="bla",
    )


def revoke_space_invitation(space, invitor, invitee):
    return mutate_update_space_user_connection_data(
        auth_user=invitor,
        space_id=space.id,
        connection_type=SpaceUserConnectionType.MEMBERSHIP_INVITEE,
        connect_action=UpdateConnectionAction.DISCONNECT,
        message="bla",
        user_id=invitee.id,
    )


def follow_space(space, follower):
    return mutate_update_space_user_connection_data(
        auth_user=follower,
        space_id=space.id,
        connection_type=SpaceUserConnectionType.FOLLOWER,
        connect_action=UpdateConnectionAction.CONNECT,
        message="bla",
    )


def unfollow_space(space, follower):
    return mutate_update_space_user_connection_data(
        auth_user=follower,
        space_id=space.id,
        connection_type=SpaceUserConnectionType.FOLLOWER,
        connect_action=UpdateConnectionAction.DISCONNECT,
        message="bla",
    )


def leave_space(space, member):
    return mutate_update_space_user_connection_data(
        auth_user=member,
        space_id=space.id,
        connection_type=SpaceUserConnectionType.MEMBER,
        connect_action=UpdateConnectionAction.LEAVE_SPACE,
        message="bla",
    )


def request_membership(space, member):
    return mutate_update_space_user_connection_data(
        auth_user=member,
        space_id=space.id,
        connection_type=SpaceUserConnectionType.MEMBERSHIP_REQUESTOR,
        connect_action=UpdateConnectionAction.CONNECT,
        message="bla",
    )


def reject_membership_request(space, admin, member):
    return mutate_update_space_user_connection_data(
        auth_user=admin,
        space_id=space.id,
        connection_type=SpaceUserConnectionType.MEMBERSHIP_REQUESTOR,
        connect_action=UpdateConnectionAction.DISCONNECT,
        message="bla",
        user_id=member.id,
    )


def approve_membership_request(space, admin, member):
    return mutate_update_space_user_connection_data(
        auth_user=admin,
        space_id=space.id,
        connection_type=SpaceUserConnectionType.MEMBER,
        connect_action=UpdateConnectionAction.CONNECT,
        message="bla",
        user_id=member.id,
    )


def grant_admin_rights(space, admin, future_admin):
    return mutate_update_space_user_connection_data(
        auth_user=admin,
        space_id=space.id,
        connection_type=SpaceUserConnectionType.ADMINISTRATOR,
        connect_action=UpdateConnectionAction.GRANT_ADMIN_ACCESS,
        message="bla",
        user_id=future_admin.id,
    )


def revoke_admin_rights(space, admin, other_admin):
    return mutate_update_space_user_connection_data(
        auth_user=admin,
        space_id=space.id,
        connection_type=SpaceUserConnectionType.ADMINISTRATOR,
        connect_action=UpdateConnectionAction.REVOKE_ADMIN_ACCESS,
        message="bla",
        user_id=other_admin.id,
    )


def remove_space_member(space, admin, member):
    return mutate_update_space_user_connection_data(
        auth_user=admin,
        space_id=space.id,
        connection_type=SpaceUserConnectionType.ADMINISTRATOR,
        connect_action=UpdateConnectionAction.REMOVE_MEMBER,
        message="bla",
        user_id=member.id,
    )


@pytest.mark.django_db
class TestSpaceEvents(TestCase):
    def setUp(self):
        initialize_tracking(PostHogConfig(api_key="fake_api_key", host="fake_host", disable_for_testing=True))

    @staticmethod
    def __input_create_task(space, skill):
        return {
            "spaceId": str(space.id),
            "name": "Valid name",
            "description": "Valid description",
            "visibility": "MEMBERS",
            "locationType": "HYBRID",
            "regularity": "REGULARLY",
            "duration": "INDETERMINATE",
            "contactEmail": "email@email.com",
            "skillsV2": [skill],
            "slotsAvailable": 1,
            "location": "Hamburg, Germany",
            "contactPhone": "+49176176176176",
        }

    @mock.patch("openbook_communities.schema.mutations.track")
    def test_tracks_space_created(self, mock_track):
        user = consenting_user()
        input_create_space = {
            "title": "valid",
            "description": "valid",
            "topicsV2": make_topics_v2(2),
            "cover": (SimpleUploadedFile(name="cover.jpg", content=simple_jpeg_bytes)),
        }
        mock_track.reset_mock()

        graphql_query = """
            mutation test($input: CreateSpaceInput!) {
                createSpace(input: $input) {
                    id
                }
            }
        """
        response = async_to_sync(schema.execute)(
            graphql_query,
            context_value=benedict({"request": {"user": user}}),
            variable_values={"input": input_create_space},
        )

        assert response.errors is None
        space_id = response.data["createSpace"]["id"]

        mock_track.assert_called_once_with(user, TrackingEvent("spaceCreated", {"spaceId": space_id}))

    @mock.patch("openbook_communities.schema.mutations.track")
    def test_tracks_space_updated(self, mock_track):
        user = consenting_user()
        space = make_space(creator=user)
        mock_track.reset_mock()

        graphql_query = """
            mutation test($input: UpdateSpaceInput!) {
                updateSpace(input: $input) {
                    onboarding { steps { text } }
                }
            }
        """
        response = async_to_sync(schema.execute)(
            graphql_query,
            context_value=benedict({"request": {"user": user}}),
            variable_values={"input": {"id": str(space.id), "title": "New Space Title"}},
        )

        assert response.errors is None

        mock_track.assert_called_once_with(user, TrackingEvent("spaceUpdated", {"spaceId": str(space.id)}))

    @mock.patch("openbook_communities.schema.mutations.track")
    def test_tracks_space_deleted(self, mock_track):
        user = consenting_user()
        space = make_space(creator=user)
        mock_track.reset_mock()

        graphql_query = """
            mutation test($id: UUID!) {
                deleteSpace(id: $id) {
                    success
                }
            }
        """
        response = async_to_sync(schema.execute)(
            graphql_query,
            context_value=benedict({"request": {"user": user}}),
            variable_values={"id": str(space.id)},
        )

        assert response.errors is None
        mock_track.assert_called_once_with(user, TrackingEvent("spaceDeleted", {"spaceId": str(space.id)}))

    @mock.patch("openbook_communities.schema.mutations.track")
    def test_tracks_space_task_created(self, mock_track):
        user = consenting_user()
        space = make_space(creator=user)
        skill = make_skill_v2()
        mock_track.reset_mock()

        graphql_query = """
            mutation test($input: CreateTaskInput!) {
                createTask(input: $input) {
                    id
                }
            }
        """
        response = async_to_sync(schema.execute)(
            graphql_query,
            context_value=benedict({"request": {"user": user}}),
            variable_values={"input": (self.__input_create_task(space, skill))},
        )

        assert response.errors is None
        task_id = response.data["createTask"]["id"]

        mock_track.assert_called_once_with(
            user, TrackingEvent("taskCreated", {"spaceId": str(space.id), "taskId": str(task_id)})
        )

    @mock.patch("openbook_communities.schema.mutations.track")
    def test_tracks_space_task_updated(self, mock_track):
        user = consenting_user()
        space = make_space(creator=user)
        skill = make_skill_v2()
        task = make_community_task(space)
        mock_track.reset_mock()

        graphql_query = """
            mutation test($input: UpdateTaskInput!) {
                updateTask(input: $input) {
                    id
                }
            }
        """

        response = async_to_sync(schema.execute)(
            graphql_query,
            context_value=benedict({"request": {"user": user}}),
            variable_values={
                "input": {
                    **(self.__input_create_task(space, skill)),
                    "taskId": str(task.id),
                }
            },
        )

        assert response.errors is None

        mock_track.assert_called_once_with(
            user, TrackingEvent("taskUpdated", {"spaceId": str(space.id), "taskId": str(task.id)})
        )

    @mock.patch("openbook_communities.schema.mutations.track")
    def test_tracks_space_task_deleted(self, mock_track):
        user = consenting_user()
        space = make_space(creator=user)
        task = make_community_task(space)
        mock_track.reset_mock()

        graphql_query = """
            mutation test($id: UUID!) {
                deleteTask(id: $id) {
                    success
                }
            }
        """

        response = async_to_sync(schema.execute)(
            graphql_query,
            context_value=benedict({"request": {"user": user}}),
            variable_values={"id": str(task.id)},
        )

        assert response.errors is None

        mock_track.assert_called_once_with(
            user, TrackingEvent("taskDeleted", {"spaceId": str(space.id), "taskId": str(task.id)})
        )

    @mock.patch("openbook_auth.models.track")
    def test_tracks_space_membership_requested(self, mock_track):
        space_creator = consenting_user()
        space = make_space(creator=space_creator)
        requestor = consenting_user()
        mock_track.reset_mock()

        self.__request_space_membership(space, requestor)

        mock_track.assert_called_once_with(
            requestor,
            TrackingEvent(
                "spaceMembershipRequestCreated", {"spaceId": str(space.id), "requestorUserId": str(requestor.id)}
            ),
        )

    @staticmethod
    def __request_space_membership(space, requestor):
        return mutate_update_space_user_connection_data(
            auth_user=requestor,
            space_id=space.id,
            connection_type=SpaceUserConnectionType.MEMBERSHIP_REQUESTOR,
            connect_action=UpdateConnectionAction.CONNECT,
            message="bla",
        )

    @staticmethod
    def __revoke_space_membership_request(space, requestor):
        return mutate_update_space_user_connection_data(
            auth_user=requestor,
            space_id=space.id,
            connection_type=SpaceUserConnectionType.MEMBERSHIP_REQUESTOR,
            connect_action=UpdateConnectionAction.DISCONNECT,
            message="bla",
        )

    @mock.patch("openbook_auth.models.track")
    def test_tracks_space_membership_request_revoked(self, mock_track):
        space_creator = consenting_user()
        space = make_space(creator=space_creator)
        requestor = consenting_user()
        self.__request_space_membership(space, requestor)
        mock_track.reset_mock()

        self.__revoke_space_membership_request(space, requestor)

        mock_track.assert_called_once_with(
            requestor,
            TrackingEvent(
                "spaceMembershipRequestRevoked",
                {"spaceId": str(space.id), "requestorUserId": str(requestor.id)},
            ),
        )

    @mock.patch("openbook_auth.models.track")
    def test_tracks_space_membership_invitation_accepted(self, mock_track):
        space_creator = consenting_user()
        space = make_space(creator=space_creator)
        invitee = consenting_user()

        invite_to_space(space, space_creator, invitee)
        accept_space_invitation(space, invitee)

        mock_track.assert_has_calls(
            [
                call(
                    space_creator,
                    TrackingEvent(
                        "spaceMembershipInvitationCreated",
                        {
                            "spaceId": str(space.id),
                            "invitingUserId": str(space_creator.id),
                            "inviteeUserId": str(invitee.id),
                        },
                    ),
                ),
                call(
                    invitee,
                    TrackingEvent(
                        "spaceMembershipInvitationAccepted",
                        {
                            "spaceId": str(space.id),
                            "invitingUserId": str(space_creator.id),
                            "inviteeUserId": str(invitee.id),
                        },
                    ),
                ),
            ]
        )

    @mock.patch("openbook_auth.models.track")
    def test_tracks_space_membership_invitation_rejected(self, mock_track):
        space_creator = consenting_user()
        space = make_space(creator=space_creator)
        invitee = consenting_user()

        invite_to_space(space, space_creator, invitee)
        reject_space_invitation(space, invitee)

        mock_track.assert_has_calls(
            [
                call(
                    space_creator,
                    TrackingEvent(
                        "spaceMembershipInvitationCreated",
                        {
                            "spaceId": str(space.id),
                            "invitingUserId": str(space_creator.id),
                            "inviteeUserId": str(invitee.id),
                        },
                    ),
                ),
                call(
                    invitee,
                    TrackingEvent(
                        "spaceMembershipInvitationRejected",
                        {
                            "spaceId": str(space.id),
                            "invitingUserId": str(space_creator.id),
                            "inviteeUserId": str(invitee.id),
                        },
                    ),
                ),
            ]
        )

    @mock.patch("openbook_auth.models.track")
    def test_tracks_space_followed(self, mock_track):
        space = make_space(creator=consenting_user())
        follower = consenting_user()
        follow_space(space, follower)
        mock_track.assert_called_once_with(follower, TrackingEvent("spaceFollowed", {"spaceId": str(space.id)}))

    @mock.patch("openbook_auth.models.track")
    def test_tracks_space_unfollowed(self, mock_track):
        space = make_space(creator=consenting_user())
        follower = consenting_user()
        follow_space(space, follower)
        unfollow_space(space, follower)
        mock_track.assert_has_calls(
            [
                call(follower, TrackingEvent("spaceFollowed", {"spaceId": str(space.id)})),
                call(follower, TrackingEvent("spaceUnfollowed", {"spaceId": str(space.id)})),
            ]
        )

    @mock.patch("openbook_auth.models.track")
    def test_tracks_space_left_by_user(self, mock_track):
        admin = consenting_user()
        space = make_space(creator=admin)
        member = consenting_user()

        request_membership(space, member)
        approve_membership_request(space, admin, member)
        mock_track.reset_mock()

        leave_space(space, member)

        mock_track.assert_called_once_with(member, TrackingEvent("spaceMemberLeft", {"spaceId": str(space.id)}))

    @mock.patch("openbook_auth.models.track")
    def test_tracks_space_membership_request_rejected_by_admin(self, mock_track):
        admin = consenting_user()
        space = make_space(creator=admin)
        requestor = consenting_user()

        request_membership(space, requestor)
        reject_membership_request(space, admin, requestor)

        mock_track.assert_has_calls(
            [
                call(
                    requestor,
                    TrackingEvent(
                        "spaceMembershipRequestCreated",
                        {"spaceId": str(space.id), "requestorUserId": str(requestor.id)},
                    ),
                ),
                call(
                    admin,
                    TrackingEvent(
                        "spaceMembershipRequestRejected",
                        {"spaceId": str(space.id), "requestorUserId": str(requestor.id)},
                    ),
                ),
            ]
        )

    @mock.patch("openbook_auth.models.track")
    def test_tracks_space_membership_request_approved_by_admin(self, mock_track):
        admin = consenting_user()
        space = make_space(creator=admin)
        requestor = consenting_user()

        request_membership(space, requestor)
        approve_membership_request(space, admin, requestor)

        mock_track.assert_has_calls(
            [
                call(
                    requestor,
                    TrackingEvent(
                        "spaceMembershipRequestCreated",
                        {"spaceId": str(space.id), "requestorUserId": str(requestor.id)},
                    ),
                ),
                call(
                    admin,
                    TrackingEvent(
                        "spaceMembershipRequestApproved",
                        {"spaceId": str(space.id), "requestorUserId": str(requestor.id)},
                    ),
                ),
            ]
        )

    @mock.patch("openbook_auth.models.track")
    def test_tracks_space_membership_invitation_revoked_by_admin(self, mock_track):
        admin = consenting_user()
        space = make_space(creator=admin)
        invitee = consenting_user()

        invite_to_space(space, admin, invitee)
        revoke_space_invitation(space, admin, invitee)

        mock_track.assert_has_calls(
            [
                call(
                    admin,
                    TrackingEvent(
                        "spaceMembershipInvitationCreated",
                        {
                            "spaceId": str(space.id),
                            "invitingUserId": str(admin.id),
                            "inviteeUserId": str(invitee.id),
                        },
                    ),
                ),
                call(
                    admin,
                    TrackingEvent(
                        "spaceMembershipInvitationRevoked",
                        {
                            "spaceId": str(space.id),
                            "invitingUserId": str(admin.id),
                            "inviteeUserId": str(invitee.id),
                        },
                    ),
                ),
            ]
        )

    @mock.patch("openbook_auth.models.track")
    def test_tracks_space_admin_rights_granted(self, mock_track):
        admin = consenting_user()
        space = make_space(creator=admin)
        future_admin = consenting_user()
        invite_to_space(space, admin, future_admin)
        accept_space_invitation(space, future_admin)
        mock_track.reset_mock()

        grant_admin_rights(space, admin, future_admin)

        mock_track.assert_called_once_with(
            admin,
            TrackingEvent(
                "spaceAdminRightsGranted", {"spaceId": str(space.id), "grantedUserId": str(future_admin.id)}
            ),
        )

    @mock.patch("openbook_auth.models.track")
    def test_tracks_space_admin_rights_revoked(self, mock_track):
        admin = consenting_user()
        space = make_space(creator=admin)
        other_admin = consenting_user()
        invite_to_space(space, admin, other_admin)
        accept_space_invitation(space, other_admin)
        grant_admin_rights(space, admin, other_admin)
        mock_track.reset_mock()

        revoke_admin_rights(space, admin, other_admin)

        mock_track.assert_called_once_with(
            admin,
            TrackingEvent("spaceAdminRightsRevoked", {"spaceId": str(space.id), "grantedUserId": str(other_admin.id)}),
        )

    @mock.patch("openbook_auth.models.track")
    def test_tracks_space_membership_removed_by_admin(self, mock_track):
        # ConnectionType.ADMINISTRATOR, Action.REMOVE_MEMBER
        admin = consenting_user()
        space = make_space(creator=admin)
        member = consenting_user()
        invite_to_space(space, admin, member)
        accept_space_invitation(space, member)
        mock_track.reset_mock()

        remove_space_member(space, admin, member)

        mock_track.assert_called_once_with(
            admin,
            TrackingEvent("spaceMemberRemoved", {"spaceId": str(space.id), "removedUserId": str(member.id)}),
        )
