import json
import logging
from unittest import TestCase
from unittest import mock
from unittest.mock import call
from uuid import uuid4

import blurhash
import pytest
from asgiref.sync import async_to_sync
from benedict import benedict
from django.conf import settings
from django.contrib.auth.models import AnonymousUser
from django.contrib.gis import geos
from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.management import call_command
from django.test import AsyncClient
from requests.models import Response

from favorites.models import FavoritableType, UserFavorite
from openbook.graphql_schema import schema
from openbook.settings import COMMUNITY_TITLE_MAX_LENGTH, COMMUNITY_DESCRIPTION_MAX_LENGTH
from openbook.tests.test_data import geolocation
from openbook_common.enums import VisibilityType
from openbook_common.tests.helpers import (
    assert_is_unauthorized,
    assert_paged_results_equal,
    create_large_image_file,
    create_video_file,
    make_community,
    make_community_task,
    make_fake_post_text,
    make_fake_post_title,
    make_user,
    simple_jpeg_bytes,
    make_topics_v2,
    make_skills_v2,
)
from openbook_common.utils.model_loaders import (
    get_community_admin_privileges_granted_notification_model,
    get_community_admin_privileges_revoked_notification_model,
    get_community_membership_revoked_notification_model,
)
from openbook_communities.enums import UpdateConnectionAction
from openbook_communities.models import (
    Community,
    CommunityNotificationsSubscription,
    SpaceUserConnectionType,
)
from openbook_communities.tests.helpers import (
    assert_onboarding,
    get_space_by_id_with_posts,
    get_space_for_user,
    mutate_invite_user_by_email,
    mutate_update_space_user_connection_data,
    mutate_update_space_user_connection_raw,
    update_and_assert_onboarding_steps,
)
from openbook_notifications.tests.helpers import get_notifications
from openbook_posts.enums import VisibilityFilter
from openbook_posts.tests.helpers import private_post_ids, public_post_ids

logger = logging.getLogger(__name__)


@pytest.fixture(scope="session")
def client():
    return AsyncClient()


@pytest.fixture(scope="session")
def django_db_setup(django_db_setup, django_db_blocker):
    with django_db_blocker.unblock():
        call_command("loaddata", "openbook_moderation/fixtures/moderation_categories.json")


@pytest.mark.django_db
class TestCommunities(TestCase):
    def test_filters_for_spaces(self):
        creator = make_user()
        [topic1, topic2] = make_topics_v2(2)
        # locations inside geolocation filter
        geolocation1 = geos.Point(8.5541567, 53.5101827, srid=4326)
        geolocation2 = geos.Point(8.5798387, 53.5590841, srid=4326)
        # location outside geolocation filter
        geolocation3 = geos.Point(9.76302, 53.5586627, srid=4326)
        space1 = make_community(creator=creator, topics_v2=[topic1, topic2], geolocation=geolocation1)
        space2 = make_community(topics_v2=[topic1], geolocation=geolocation2)
        space3 = make_community(topics_v2=[topic2], geolocation=geolocation3)
        [skill1, skill2, skill3] = make_skills_v2(3)
        make_community_task(space1, skills_v2=[skill1, skill2])
        make_community_task(space2, skills_v2=[skill2, skill3])
        make_community_task(space3, skills_v2=[skill3])

        filter_query = """
            query($geolocation: GeoJSON, $memberId: UUID, $topicsV2: [String!], $skillsV2: [String!]) {
                spaces(geolocation: $geolocation, memberId: $memberId, topicsV2: $topicsV2, skillsV2: $skillsV2) {
                    totalResults
                    data {
                        id
                    }
                }
            }
        """

        def transform_space(space):
            return {"id": str(space.id)}

        def assert_filtered_spaces(filter_options, expected_spaces):
            filter_response = async_to_sync(schema.execute)(filter_query, variable_values=filter_options)
            expected_data = list(map(transform_space, expected_spaces))
            assert_paged_results_equal(filter_response.data["spaces"], expected_data)

        # Return all spaces for empty filter
        assert_filtered_spaces({}, [space1, space2, space3])

        # Filter by common topic
        assert_filtered_spaces({"topicsV2": [topic1]}, [space1, space2])

        # Filter by unique topic
        assert_filtered_spaces({"topicsV2": [topic2]}, [space1, space3])

        # Filter by location
        assert_filtered_spaces({"geolocation": geolocation}, [space1, space2])

        # Filter by topic and location
        assert_filtered_spaces({"topicsV2": [topic2], "geolocation": geolocation}, [space1])

        # Filter by single skill
        assert_filtered_spaces({"skillsV2": [skill1]}, [space1])

        # Filter by multiple skills
        assert_filtered_spaces({"skillsV2": [skill1, skill2]}, [space1, space2])

        # Filter by skills and location
        assert_filtered_spaces({"skillsV2": [skill3], "geolocation": geolocation}, [space2])

        # Filter by skills and topics
        assert_filtered_spaces({"skillsV2": [skill2], "topicsV2": [topic2]}, [space1])

        # Filter by member id
        assert_filtered_spaces({"memberId": creator.username}, [space1])
        assert_filtered_spaces({"memberId": creator.username, "geolocation": geolocation}, [space1])

        # Filter by skills, topics and location
        assert_filtered_spaces(
            {
                "skillsV2": [skill3],
                "geolocation": geolocation,
                "topicsV2": [topic2],
            },
            [],
        )

        # Filter by skills V2 and topics V2
        assert_filtered_spaces(
            {
                "skillsV2": [skill2],
                "topicsV2": [topic1],
            },
            [space1, space2],
        )

    def test_filters_for_discover_spaces(self):
        [topic1, topic2] = make_topics_v2(2)
        # locations inside geolocation filter
        geolocation1 = geos.Point(8.5541567, 53.5101827, srid=4326)
        geolocation2 = geos.Point(8.5798387, 53.5590841, srid=4326)
        # location outside geolocation filter
        geolocation3 = geos.Point(9.76302, 53.5586627, srid=4326)
        space1 = make_community(topics_v2=[topic1, topic2], geolocation=geolocation1)
        space2 = make_community(topics_v2=[topic1], geolocation=geolocation2)
        space3 = make_community(topics_v2=[topic2], geolocation=geolocation3)
        make_community(topics_v2=[topic1], geolocation=geolocation2, is_deleted=True)  # deleted spaces are not shown
        [skill1, skill2, skill3] = make_skills_v2(3)
        make_community_task(space1, skills_v2=[skill1, skill2])
        make_community_task(space2, skills_v2=[skill2, skill3])

        filter_query = """
            query($geolocation: GeoJSON, $topicsV2: [String!], $skillsV2: [String!]) {
                discoverSpaces(geolocation: $geolocation, topicsV2: $topicsV2, skillsV2: $skillsV2) {
                    topicV2
                    skillV2
                    locationId
                    spaces {
                        totalResults
                        data {
                            id
                        }
                    }
                }
            }
        """

        def transform_space(space):
            return {"id": str(space.id)}

        def assert_filtered_spaces(filter_options, expected_spaces):
            filter_response = async_to_sync(schema.execute)(
                filter_query,
                variable_values=filter_options,
                context_value=benedict({"request": {"user": AnonymousUser}}),
            )
            expected_data = list(map(transform_space, expected_spaces))
            assert_paged_results_equal(
                filter_response.data["discoverSpaces"][0]["spaces"],
                expected_data,
            )

        # Filter by common topic
        assert_filtered_spaces({"topicsV2": [topic1]}, [space1, space2])

        # Filter by unique topic
        assert_filtered_spaces({"topicsV2": [topic2]}, [space1, space3])

        # Filter by topics, skills and geolocation
        filter_response = async_to_sync(schema.execute)(
            filter_query,
            variable_values={
                "topicsV2": [topic1, topic2],
                "skillsV2": [skill3],
                "geolocation": geolocation,
            },
            context_value=benedict({"request": {"user": AnonymousUser}}),
        )
        assert len(filter_response.data["discoverSpaces"]) == 4
        location, t1, t2, skill = (
            (0, 1, 2, 3) if filter_response.data["discoverSpaces"][1]["topicV2"] == topic1 else (0, 2, 1, 3)
        )

        assert_paged_results_equal(
            filter_response.data["discoverSpaces"][location]["spaces"],
            list(map(transform_space, [space1, space2])),
        )
        assert_paged_results_equal(
            filter_response.data["discoverSpaces"][t1]["spaces"],
            list(map(transform_space, [space1, space2])),
        )
        assert_paged_results_equal(
            filter_response.data["discoverSpaces"][t2]["spaces"],
            list(map(transform_space, [space1, space3])),
        )
        assert_paged_results_equal(
            filter_response.data["discoverSpaces"][skill]["spaces"],
            list(map(transform_space, [space2])),
        )

        # Filter by topics V2, skills V2 and geolocation
        filter_response = async_to_sync(schema.execute)(
            filter_query,
            variable_values={
                "topicsV2": [topic1, topic2],
                "skillsV2": [skill3],
                "geolocation": geolocation,
            },
            context_value=benedict({"request": {"user": AnonymousUser}}),
        )
        assert len(filter_response.data["discoverSpaces"]) == 4
        location, t1, t2, skill = (
            (0, 1, 2, 3) if filter_response.data["discoverSpaces"][1]["topicV2"] == topic1 else (0, 2, 1, 3)
        )

        assert_paged_results_equal(
            filter_response.data["discoverSpaces"][location]["spaces"],
            list(map(transform_space, [space1, space2])),
        )
        assert_paged_results_equal(
            filter_response.data["discoverSpaces"][t1]["spaces"],
            list(map(transform_space, [space1, space2])),
        )
        assert_paged_results_equal(
            filter_response.data["discoverSpaces"][t2]["spaces"],
            list(map(transform_space, [space1, space3])),
        )
        assert_paged_results_equal(
            filter_response.data["discoverSpaces"][skill]["spaces"],
            list(map(transform_space, [space2])),
        )

    def test_my_spaces(self):
        creator1 = make_user()
        creator2 = make_user()
        creator3 = make_user()

        space_creator = make_community(creator=creator1)

        space_member = make_community(creator=creator2)
        creator2.invite_user_to_community(user=creator1, community=space_member)
        creator1.accept_membership_invite_to_community_for_username(space_member.name)

        space_follower = make_community()
        creator1.enable_new_post_notifications_for_community_with_name(space_follower.name)

        space_request_membership = make_community()
        creator1.request_membership_to_community_with_name(community_name=space_request_membership.name)

        space_invited = make_community(creator=creator3)
        creator3.invite_user_to_community(user=creator1, community=space_invited)

        # repeat the setup with deleted space to ensure they are not shown
        make_community(creator=creator1, is_deleted=True)  # deleted space is not shown

        space_deleted_member = make_community(creator=creator2, is_deleted=True)  # deleted space is not shown
        creator2.invite_user_to_community(user=creator1, community=space_deleted_member)
        creator1.accept_membership_invite_to_community_for_username(space_deleted_member.name)

        space_deleted_follower = make_community(is_deleted=True)  # deleted space is not shown
        creator1.enable_new_post_notifications_for_community_with_name(space_deleted_follower.name)

        space_deleted_request_membership = make_community(is_deleted=True)  # deleted space is not shown
        creator1.request_membership_to_community_with_name(community_name=space_deleted_request_membership.name)

        space_deleted_invite = make_community(creator=creator2, is_deleted=True)  # deleted space is not shown
        creator2.invite_user_to_community(user=creator1, community=space_deleted_invite)

        response = async_to_sync(schema.execute)(
            """
            query {
                mySpaces {
                    section
                    type
                    spaces {
                        totalResults
                        data {
                            id
                        }
                    }
                }
            }
            """,
            context_value=benedict({"request": {"user": creator1}}),
        ).data["mySpaces"]

        assert len(response) == 5

        created_section = response[0]
        assert created_section["section"] == "Created"
        assert created_section["type"] == SpaceUserConnectionType.CREATOR.value
        assert created_section["spaces"]["totalResults"] == 1
        assert created_section["spaces"]["data"][0]["id"] == str(space_creator.id)

        joined_section = response[1]
        assert joined_section["section"] == "Joined"
        assert joined_section["type"] == SpaceUserConnectionType.MEMBER.value
        assert joined_section["spaces"]["totalResults"] == 1
        assert joined_section["spaces"]["data"][0]["id"] == str(space_member.id)

        requested_section = response[2]
        assert requested_section["section"] == "Requested"
        assert requested_section["type"], SpaceUserConnectionType.MEMBERSHIP_REQUESTOR.value
        assert requested_section["spaces"]["totalResults"] == 1
        assert requested_section["spaces"]["data"][0]["id"] == str(space_request_membership.id)

        invited_section = response[3]
        assert invited_section["section"] == "Invited"
        assert invited_section["type"], SpaceUserConnectionType.MEMBERSHIP_INVITEE.value
        assert invited_section["spaces"]["totalResults"] == 1
        assert invited_section["spaces"]["data"][0]["id"] == str(space_invited.id)

        following_section = response[4]
        assert following_section["section"] == "Following"
        assert following_section["type"], SpaceUserConnectionType.FOLLOWER.value
        assert following_section["spaces"]["totalResults"] == 1
        assert following_section["spaces"]["data"][0]["id"] == str(space_follower.id)

    @mock.patch("openbook_communities.schema.mutations.invalidate_discover_spaces_query_cache")
    @mock.patch("openbook_communities.schema.mutations.publish_space_user_added_event")
    @mock.patch("openbook_notifications.services.NotificationsService.send_space_membership_request_notification")
    @mock.patch(
        "openbook_notifications.services.NotificationsService.send_space_membership_request_approval_user_notification"
    )
    @mock.patch("openbook_notifications.api.NotificationApi.cancel_workflow")
    @mock.patch("openbook_notifications.api.NotificationApi.delete_in_app_messages")
    @mock.patch(
        "openbook_notifications.services.NotificationsService.send_space_membership_request_approval_admin_notification"
    )
    def test_space_membership_request_approval_process(
        self,
        mock_send_space_membership_request_approval_admin_notification,
        mock_notification_api_delete_in_app_messages,
        mock_notification_api_cancel_workflow,
        mock_send_space_membership_request_approval_user_notification,
        mock_send_space_membership_request_notification,
        mock_publish_space_user_added_event,
        mock_invalidate_discover_spaces_query_cache,
    ):
        # GIVEN a space with a creator
        membership_requestor = make_user()
        space_creator = make_user()
        space = make_community(creator=space_creator)
        mock_publish_space_user_added_event.return_value = None

        def member_result(user, is_admin):
            return {
                "user": {"id": user.username},
                "isAdministrator": is_admin,
            }

        # GIVEN preconditions
        pre_join_space = get_space_for_user(membership_requestor, space)
        assert pre_join_space["connectionStatusToMyself"] == []
        assert_paged_results_equal(pre_join_space["members"], [member_result(space_creator, is_admin=True)])

        data = get_notifications(membership_requestor)
        assert data["totalResults"] == 0
        data = get_notifications(space_creator)
        assert data["totalResults"] == 0

        # WHEN sending a join request
        message = "helløj"
        after_request_space = mutate_update_space_user_connection_data(
            auth_user=membership_requestor,
            space_id=space.id,
            connection_type=SpaceUserConnectionType.MEMBERSHIP_REQUESTOR,
            connect_action=UpdateConnectionAction.CONNECT,
            message=message,
        )

        assert len(after_request_space["connectionStatusToMyself"]), len(
            [SpaceUserConnectionType.MEMBERSHIP_REQUESTOR.value, SpaceUserConnectionType.FOLLOWER.value]
        )

        # THEN staff should receive MembershipRequest notification
        staff_request_received_notification = get_notifications(space_creator)["data"][0]
        assert staff_request_received_notification["notificationType"] == "CMR"
        assert staff_request_received_notification["options"]["space"]["title"] == space.title
        assert (
            staff_request_received_notification["options"]["user"]["fullName"]
            == membership_requestor.profile.full_name()
        )
        assert staff_request_received_notification["options"]["message"] == message

        # THEN a membership request should be created
        membership_request = space.get_membership_request(membership_requestor)

        # THEN admin should receive notification via Notifications system
        mock_send_space_membership_request_notification.assert_called_once()
        request_kwargs = mock_send_space_membership_request_notification.call_args.kwargs
        request_recipients = [space_creator.username]

        self.assertEqual([r.username for r in request_kwargs["recipients"]], request_recipients)
        self.assertEqual(request_kwargs["requester"], membership_requestor)
        self.assertEqual(request_kwargs["space"], space)
        self.assertEqual(request_kwargs["message"], message)

        # WHEN space creator approves user join request
        space_after_approval = mutate_update_space_user_connection_data(
            auth_user=space_creator,
            user_id=membership_requestor.username,
            space_id=space.id,
            connection_type=SpaceUserConnectionType.MEMBER,
            connect_action=UpdateConnectionAction.CONNECT,
        )

        community = Community.objects.get(id=space.id)
        mock_publish_space_user_added_event.assert_called_once_with(
            username=membership_requestor.username, community=community
        )
        assert_paged_results_equal(
            space_after_approval["members"],
            [member_result(space_creator, is_admin=True), member_result(membership_requestor, is_admin=False)],
        )

        # THEN user has correct connection status
        assert len(get_space_for_user(membership_requestor, space)["connectionStatusToMyself"]) == len(
            [SpaceUserConnectionType.MEMBER.value, SpaceUserConnectionType.FOLLOWER.value]
        )

        # THEN user has approval notification
        membership_requestor_notifications = get_notifications(membership_requestor)
        assert membership_requestor_notifications["totalResults"] == 1
        assert membership_requestor_notifications["data"][0]["notificationType"] == "CMRA"

        # THEN user should receive notification via Notifications system
        mock_send_space_membership_request_approval_user_notification.assert_called_once()
        approval_kwargs = mock_send_space_membership_request_approval_user_notification.call_args.kwargs

        self.assertEqual(approval_kwargs["requester"], membership_requestor)
        self.assertEqual(approval_kwargs["space"], space)
        self.assertEqual(approval_kwargs["approver"], space_creator)

        # THEN space membership request workflow should be cancelled to avoid sending emails to staff members
        mock_notification_api_cancel_workflow.assert_called_once_with(transaction_id=str(membership_request.id))

        # THEN in-app messages should be deleted
        mock_notification_api_delete_in_app_messages.assert_called_once_with(transaction_id=str(membership_request.id))

        # THEN staff has approval notification
        staff_notifications = get_notifications(space_creator)
        assert staff_notifications["totalResults"] == 1
        assert staff_notifications["data"][0]["notificationType"] == "CMRA"
        assert staff_notifications["data"][0]["options"]["space"]["title"] == space.title
        assert (
            staff_notifications["data"][0]["options"]["user"]["fullName"] == membership_requestor.profile.full_name()
        )

        # THEN staff should receive notification via Notifications system
        kwargs = mock_send_space_membership_request_approval_admin_notification.call_args.kwargs
        expected_recipients = [space_creator.username]

        self.assertEqual([r.username for r in kwargs["recipients"]], expected_recipients)
        self.assertEqual(kwargs["requester"], membership_requestor)
        self.assertEqual(kwargs["space"], space)

        mock_invalidate_discover_spaces_query_cache.assert_called()

    @mock.patch("openbook_notifications.api.NotificationApi.cancel_workflow")
    @mock.patch("openbook_notifications.api.NotificationApi.delete_in_app_messages")
    def test_space_membership_request_approval_user_process_with_invite_to_same_user(
        self,
        mock_notification_api_delete_in_app_messages,
        mock_notification_api_cancel_workflow,
    ):
        invitee_email = "test@test.com"
        invitee = make_user(email=invitee_email)
        space_creator = make_user()
        space = make_community(creator=space_creator)

        def member_result(user, is_admin):
            return {
                "user": {"id": user.username},
                "isAdministrator": is_admin,
            }

        # Create a Membership Request
        mutate_update_space_user_connection_data(
            auth_user=invitee,
            space_id=space.id,
            connection_type=SpaceUserConnectionType.MEMBERSHIP_REQUESTOR,
            connect_action=UpdateConnectionAction.CONNECT,
        )

        # Send Invite Request
        mutate_invite_user_by_email(
            auth_user=space_creator,
            email=invitee_email,
            space_id=space.id,
        )

        # THEN a membership request should be created
        membership_request = space.get_membership_request(invitee)

        # THEN an invite object should have been created
        invite = space.get_membership_invite(invitee)

        # Approve user Membership Request
        space_after_approval = mutate_update_space_user_connection_data(
            auth_user=space_creator,
            user_id=invitee.username,
            space_id=space.id,
            connection_type=SpaceUserConnectionType.MEMBER,
            connect_action=UpdateConnectionAction.CONNECT,
        )

        assert_paged_results_equal(
            space_after_approval["members"],
            [member_result(space_creator, is_admin=True), member_result(invitee, is_admin=False)],
        )

        user_space = get_space_for_user(invitee, space)

        # User has correct connection statuses (there should be more if invitation was still present)
        assert len(user_space["connectionStatusToMyself"]) == len(
            [SpaceUserConnectionType.MEMBER.value, SpaceUserConnectionType.FOLLOWER.value]
        )
        assert SpaceUserConnectionType.MEMBER.value in user_space["connectionStatusToMyself"]
        assert SpaceUserConnectionType.FOLLOWER.value in user_space["connectionStatusToMyself"]

        # THEN invite and membership request workflows should be cancelled
        mock_notification_api_cancel_workflow.assert_has_calls(
            [mock.call(transaction_id=str(membership_request.id)), mock.call(transaction_id=str(invite.id))]
        )

        # THEN in-app messages should be deleted
        mock_notification_api_delete_in_app_messages.assert_has_calls(
            [mock.call(transaction_id=str(membership_request.id)), mock.call(transaction_id=str(invite.id))]
        )

    @mock.patch("openbook_communities.schema.mutations.invalidate_discover_spaces_query_cache")
    @mock.patch("openbook_communities.schema.mutations.publish_space_user_added_event")
    @mock.patch("openbook_notifications.services.NotificationsService.send_space_membership_request_notification")
    def test_space_membership_request_with_message(
        self,
        mock_send_space_membership_request_notification,
        mock_publish_space_user_added_event,
        mock_invalidate_discover_spaces_query_cache,
    ):
        membership_requestor = make_user()
        space_creator = make_user()
        admin = make_user()
        moderator = make_user()
        space = make_community(creator=space_creator, admins=[admin], moderators=[moderator])
        mock_publish_space_user_added_event.return_value = None
        message = "I'd love to join!"

        def member_result(user, is_admin):
            return {
                "user": {"id": user.username},
                "isAdministrator": is_admin,
            }

        # GIVEN a space with a creator, an additional admin and a moderator
        pre_join_space = get_space_for_user(membership_requestor, space)
        assert pre_join_space["connectionStatusToMyself"] == []
        assert_paged_results_equal(
            pre_join_space["members"],
            [
                member_result(space_creator, is_admin=True),
                member_result(admin, is_admin=True),
                member_result(moderator, is_admin=False),
            ],
        )

        data = get_notifications(membership_requestor)
        assert data["totalResults"] == 0
        data = get_notifications(space_creator)
        assert data["totalResults"] == 0

        # WHEN sending a join request
        after_request_space = mutate_update_space_user_connection_data(
            auth_user=membership_requestor,
            space_id=space.id,
            connection_type=SpaceUserConnectionType.MEMBERSHIP_REQUESTOR,
            connect_action=UpdateConnectionAction.CONNECT,
            message=message,
        )

        assert len(after_request_space["connectionStatusToMyself"]), len(
            [SpaceUserConnectionType.MEMBERSHIP_REQUESTOR.value, SpaceUserConnectionType.FOLLOWER.value]
        )

        # THEN staff received MembershipRequest notification with message
        staff_request_received_notification = get_notifications(space_creator)["data"][0]
        assert staff_request_received_notification["notificationType"] == "CMR"
        assert staff_request_received_notification["options"]["space"]["title"] == space.title
        assert (
            staff_request_received_notification["options"]["user"]["fullName"]
            == membership_requestor.profile.full_name()
        )
        assert staff_request_received_notification["options"]["message"] == message

        # THEN staff received notification via Notifications system
        mock_send_space_membership_request_notification.assert_called_once()
        kwargs = mock_send_space_membership_request_notification.call_args.kwargs
        expected_recipients = [space_creator.username, admin.username, moderator.username]

        self.assertEqual([r.username for r in kwargs["recipients"]], expected_recipients)
        self.assertEqual(kwargs["requester"], membership_requestor)
        self.assertEqual(kwargs["space"], space)
        self.assertEqual(kwargs["message"], message)

    def test_validates_space_membership_request(self):
        membership_requestor = make_user()
        space_creator = make_user()
        space = make_community(creator=space_creator)
        message = "I'd love to join!"

        invalid_uuid = str(uuid4())

        expected_errors = [
            {"field": "space_id", "value": None, "expected_error": "badly formed hexadecimal UUID string"},
            {
                "field": "space_id",
                "value": invalid_uuid,
                "expected_error": "No community with the provided id exists.",
            },
            {"field": "message", "value": "f" * 1001, "expected_code": "max_length"},
        ]

        for test_case in expected_errors:
            response = mutate_update_space_user_connection_raw(
                auth_user=membership_requestor,
                space_id=test_case["value"] if test_case["field"] == "space_id" else space.id,
                connection_type=SpaceUserConnectionType.MEMBERSHIP_REQUESTOR,
                connect_action=UpdateConnectionAction.CONNECT,
                message=test_case["value"] if test_case["field"] == "message" else message,
            )
            if "expected_code" in test_case:
                field_errors = json.loads(response.errors[0].extensions["errors"])
                assert test_case["expected_code"] == field_errors[test_case["field"]][0]["code"]
            else:
                assert test_case["expected_error"] in str(response.errors[0].message)
            assert (response.data["updateSpaceUserConnection"] if response.data else response.data) is None

    @mock.patch("openbook_communities.schema.mutations.invalidate_discover_spaces_query_cache")
    @mock.patch("openbook_communities.schema.mutations.publish_space_user_added_event")
    @mock.patch("openbook_notifications.services.NotificationsService.send_space_membership_request_notification")
    @mock.patch(
        "openbook_notifications.services.NotificationsService.send_space_membership_request_decline_user_notification"
    )
    @mock.patch(
        "openbook_notifications.services.NotificationsService.send_space_membership_request_decline_admin_notification"
    )
    @mock.patch("openbook_notifications.api.NotificationApi.cancel_workflow")
    @mock.patch("openbook_notifications.api.NotificationApi.delete_in_app_messages")
    def test_space_membership_request_rejection_process(
        self,
        mock_notification_api_delete_in_app_messages,
        mock_notification_api_cancel_workflow,
        mock_send_space_membership_request_decline_admin_notification,
        mock_send_space_membership_request_decline_user_notification,
        mock_send_space_membership_request_notification,
        mock_publish_space_user_added_event,
        mock_invalidate_discover_spaces_query_cache,
    ):
        # GIVEN a space with a creator
        membership_requestor = make_user()
        space_creator = make_user()
        space = make_community(creator=space_creator)

        def member_result(user, is_admin):
            return {
                "user": {"id": user.username},
                "isAdministrator": is_admin,
            }

        # GIVEN preconditions
        pre_join_space = get_space_for_user(membership_requestor, space)
        assert pre_join_space["connectionStatusToMyself"] == []
        assert_paged_results_equal(pre_join_space["members"], [member_result(space_creator, is_admin=True)])

        data = get_notifications(membership_requestor)
        assert data["totalResults"] == 0
        data = get_notifications(space_creator)
        assert data["totalResults"] == 0

        # WHEN sending a join request
        message = "helløj"
        after_request_space = mutate_update_space_user_connection_data(
            auth_user=membership_requestor,
            space_id=space.id,
            connection_type=SpaceUserConnectionType.MEMBERSHIP_REQUESTOR,
            connect_action=UpdateConnectionAction.CONNECT,
            message=message,
        )

        assert len(after_request_space["connectionStatusToMyself"]) == len(
            [SpaceUserConnectionType.MEMBERSHIP_REQUESTOR.value, SpaceUserConnectionType.FOLLOWER.value]
        )

        # THEN a membership request should be created
        membership_request = space.get_membership_request(membership_requestor)

        # THEN staff should receive a MembershipRequest notification
        staff_request_received_notification = get_notifications(space_creator)["data"][0]
        assert staff_request_received_notification["notificationType"] == "CMR"
        assert staff_request_received_notification["options"]["space"]["title"] == space.title
        assert (
            staff_request_received_notification["options"]["user"]["fullName"]
            == membership_requestor.profile.full_name()
        )

        # THEN admin should receive notification via Notifications system
        mock_send_space_membership_request_notification.assert_called_once()
        kwargs = mock_send_space_membership_request_notification.call_args.kwargs
        expected_recipients = [space_creator.username]

        self.assertEqual([r.username for r in kwargs["recipients"]], expected_recipients)
        self.assertEqual(kwargs["requester"], membership_requestor)
        self.assertEqual(kwargs["space"], space)
        self.assertEqual(kwargs["message"], message)

        # WHEN admin rejects user membership request
        space_after_rejection = mutate_update_space_user_connection_data(
            auth_user=space_creator,
            user_id=membership_requestor.username,
            space_id=space.id,
            connection_type=SpaceUserConnectionType.MEMBERSHIP_REQUESTOR,
            connect_action=UpdateConnectionAction.DISCONNECT,
        )

        assert_paged_results_equal(
            space_after_rejection["members"],
            [member_result(space_creator, is_admin=True)],
        )

        # THEN user has correct connection status
        assert len(get_space_for_user(membership_requestor, space)["connectionStatusToMyself"]) == len(
            [SpaceUserConnectionType.FOLLOWER.value]
        )

        # THEN user has no notification
        membership_requestor_notifications = get_notifications(membership_requestor)
        assert membership_requestor_notifications["totalResults"] == 0

        # THEN staff has no notification
        staff_notifications = get_notifications(space_creator)
        assert staff_notifications["totalResults"] == 0

        # THEN space membership request workflow should be cancelled to avoid sending emails to staff members
        mock_notification_api_cancel_workflow.assert_called_once_with(transaction_id=str(membership_request.id))

        # THEN in-app messages should be deleted
        mock_notification_api_delete_in_app_messages.assert_called_once_with(transaction_id=str(membership_request.id))

        # THEN user should receive notification via Notifications system
        mock_send_space_membership_request_decline_user_notification.assert_called_once()
        kwargs = mock_send_space_membership_request_decline_user_notification.call_args.kwargs

        self.assertEqual(kwargs["requester"], membership_requestor)
        self.assertEqual(kwargs["space"], space)
        self.assertEqual(kwargs["denier"], space_creator)

        # THEN admin should receive notification via Notifications system
        mock_send_space_membership_request_decline_admin_notification.assert_called_once()
        kwargs = mock_send_space_membership_request_decline_admin_notification.call_args.kwargs
        expected_recipients = [space_creator.username]

        self.assertEqual([r.username for r in kwargs["recipients"]], expected_recipients)
        self.assertEqual(kwargs["requester"], membership_requestor)
        self.assertEqual(kwargs["space"], space)
        self.assertEqual(kwargs["denier"], space_creator)

        mock_publish_space_user_added_event.assert_not_called()
        mock_invalidate_discover_spaces_query_cache.assert_called()

    @mock.patch("openbook_notifications.services.NotificationsService.send_space_membership_request_notification")
    def test_space_membership_request_only_visible_to_admins(self, mock_send_space_membership_request_notification):
        # GIVEN a space with an admin and other users
        user = make_user()
        member = make_user()
        admin = make_user()
        membership_requestor = make_user()
        community = make_community(creator=admin)
        community.add_member(member)
        message = "helløj"

        # WHEN sending a join request
        mutate_update_space_user_connection_data(
            auth_user=membership_requestor,
            space_id=community.id,
            connection_type=SpaceUserConnectionType.MEMBERSHIP_REQUESTOR,
            connect_action=UpdateConnectionAction.CONNECT,
            message=message,
        )

        space_by_id_query = f"""
            query {{
                spaceById(idOrName: "{community.name}") {{
                    membershipRequests {{
                        totalResults
                        data {{
                            id
                            user {{
                                id
                            }}
                        }}
                    }}
                    members {{
                        totalResults
                        data {{
                            id
                        }}
                    }}
                }}
            }}
            """

        # THEN admin should get the membershipRequests
        response_admin = async_to_sync(schema.execute)(
            space_by_id_query,
            context_value=benedict({"request": {"user": admin}}),
        )
        assert response_admin.errors is None
        paged_membership_requests = response_admin.data["spaceById"]["membershipRequests"]
        assert paged_membership_requests["totalResults"] == 1

        # THEN non-admin member should get zero membershipRequests
        response_member = async_to_sync(schema.execute)(
            space_by_id_query,
            context_value=benedict({"request": {"user": member}}),
        )
        assert response_member.errors is None
        paged_membership_requests = response_member.data["spaceById"]["membershipRequests"]
        assert paged_membership_requests["totalResults"] == 0

        # THEN non-member should get zero membershipRequests
        response_non_member = async_to_sync(schema.execute)(
            space_by_id_query,
            context_value=benedict({"request": {"user": user}}),
        )
        assert response_non_member.errors is None
        paged_membership_requests = response_non_member.data["spaceById"]["membershipRequests"]
        assert paged_membership_requests["totalResults"] == 0

        # THEN anonymous user should get zero membershipRequests
        response_non_member = async_to_sync(schema.execute)(
            space_by_id_query,
            context_value=benedict({"request": {"user": AnonymousUser}}),
        )
        assert response_non_member.errors is None
        paged_members = response_non_member.data["spaceById"]["membershipRequests"]
        assert paged_members["totalResults"] == 0

        # THEN admin should receive notification via Notifications system
        mock_send_space_membership_request_notification.assert_called_once()
        kwargs = mock_send_space_membership_request_notification.call_args.kwargs
        expected_recipients = [admin.username]

        self.assertEqual([r.username for r in kwargs["recipients"]], expected_recipients)
        self.assertEqual(kwargs["requester"], membership_requestor)
        self.assertEqual(kwargs["space"], community)
        self.assertEqual(kwargs["message"], message)

    def test_space_invites_only_visible_to_admins(
        self,
    ):
        invitee_email = "test@test.com"
        invitee = make_user(email=invitee_email)
        member = make_user()
        non_member = make_user()
        space_creator = make_user()
        space = make_community(creator=space_creator)
        space.add_member(member)

        # Send Invite Request
        mutate_invite_user_by_email(
            auth_user=space_creator,
            email=invitee_email,
            space_id=space.id,
        )

        # Invited user has invitee status
        assert get_space_for_user(invitee, space)["connectionStatusToMyself"] == [
            SpaceUserConnectionType.MEMBERSHIP_INVITEE.value
        ]

        # Prepare query to check for each user
        space_by_id_query = f"""
            query {{
                spaceById(idOrName: "{space.name}") {{
                    invites {{
                        totalResults
                        data {{
                            id
                            invitedUser {{
                                id
                            }}
                        }}
                    }}
                    members {{
                        totalResults
                        data {{
                            id
                        }}
                    }}
                }}
            }}
            """

        # THEN admin should get the invites
        response_admin = async_to_sync(schema.execute)(
            space_by_id_query,
            context_value=benedict({"request": {"user": space_creator}}),
        )
        assert response_admin.errors is None
        paged_invites = response_admin.data["spaceById"]["invites"]
        assert paged_invites["totalResults"] == 1

        # THEN non-admin member should get zero invites
        response_member = async_to_sync(schema.execute)(
            space_by_id_query,
            context_value=benedict({"request": {"user": member}}),
        )
        assert response_member.errors is None
        paged_invites = response_member.data["spaceById"]["invites"]
        assert paged_invites["totalResults"] == 0

        # THEN non-member should get zero invites
        response_non_member = async_to_sync(schema.execute)(
            space_by_id_query,
            context_value=benedict({"request": {"user": non_member}}),
        )
        assert response_non_member.errors is None
        paged_invites = response_non_member.data["spaceById"]["invites"]
        assert paged_invites["totalResults"] == 0

        # THEN anonymous user should get zero invites
        response_non_member = async_to_sync(schema.execute)(
            space_by_id_query,
            context_value=benedict({"request": {"user": AnonymousUser}}),
        )
        assert response_non_member.errors is None
        paged_members = response_non_member.data["spaceById"]["invites"]
        assert paged_members["totalResults"] == 0

    def test_space_admin_withdraw_invite_success(
        self,
    ):
        invitee_email = "test@test.com"
        invitee = make_user(email=invitee_email)
        member = make_user()
        space_creator = make_user()
        space = make_community(creator=space_creator)
        space.add_member(member)

        # Send Invite Request
        mutate_invite_user_by_email(
            auth_user=space_creator,
            email=invitee_email,
            space_id=space.id,
        )

        # Invited user has invitee status
        assert get_space_for_user(invitee, space)["connectionStatusToMyself"] == [
            SpaceUserConnectionType.MEMBERSHIP_INVITEE.value
        ]

        # Prepare query to check for each user
        space_by_id_query = f"""
            query {{
                spaceById(idOrName: "{space.name}") {{
                    invites {{
                        totalResults
                        data {{
                            id
                            invitedUser {{
                                id
                            }}
                        }}
                    }}
                    members {{
                        totalResults
                        data {{
                            id
                        }}
                    }}
                }}
            }}
            """

        # THEN admin should get the invites
        response_admin = async_to_sync(schema.execute)(
            space_by_id_query,
            context_value=benedict({"request": {"user": space_creator}}),
        )
        assert response_admin.errors is None
        paged_invites = response_admin.data["spaceById"]["invites"]
        assert paged_invites["totalResults"] == 1

        # THEN Admin withdraws invite
        mutate_update_space_user_connection_data(
            auth_user=space_creator,
            space_id=space.id,
            connection_type=SpaceUserConnectionType.MEMBERSHIP_INVITEE,
            connect_action=UpdateConnectionAction.DISCONNECT,
            user_id=invitee.username,
        )

        # THEN admin should get zero invites
        response_admin = async_to_sync(schema.execute)(
            space_by_id_query,
            context_value=benedict({"request": {"user": space_creator}}),
        )
        assert response_admin.errors is None
        paged_invites = response_admin.data["spaceById"]["invites"]
        assert paged_invites["totalResults"] == 0

    # TODO
    def test_space_admin_withdraw_invite_error(
        self,
    ):
        invitee_email = "test@test.com"
        invitee = make_user(email=invitee_email)
        member = make_user()
        non_invitee = make_user()
        non_member = make_user()
        space_creator = make_user()
        space = make_community(creator=space_creator)
        space.add_member(member)

        # Send Invite Request
        mutate_invite_user_by_email(
            auth_user=space_creator,
            email=invitee_email,
            space_id=space.id,
        )

        # Invited user has invitee status
        assert get_space_for_user(invitee, space)["connectionStatusToMyself"] == [
            SpaceUserConnectionType.MEMBERSHIP_INVITEE.value
        ]

        # THEN Admin withdraws invite of non-invitee (error)
        response_admin = mutate_update_space_user_connection_raw(
            auth_user=space_creator,
            space_id=space.id,
            connection_type=SpaceUserConnectionType.MEMBERSHIP_INVITEE,
            connect_action=UpdateConnectionAction.DISCONNECT,
            user_id=non_invitee.username,
        )
        assert response_admin.data is None
        assert response_admin.errors is not None
        assert "No invite to withdraw." in response_admin.errors[0].extensions["errors"]

        # THEN non-admin withdraws invite of invitee (error)
        response_non_admin = mutate_update_space_user_connection_raw(
            auth_user=member,
            space_id=space.id,
            connection_type=SpaceUserConnectionType.MEMBERSHIP_INVITEE,
            connect_action=UpdateConnectionAction.DISCONNECT,
            user_id=invitee.username,
        )
        assert response_non_admin.data is None
        assert response_non_admin.errors is not None

        # THEN non-member withdraws invite of invitee (error)
        response_non_member = mutate_update_space_user_connection_raw(
            auth_user=non_member,
            space_id=space.id,
            connection_type=SpaceUserConnectionType.MEMBERSHIP_INVITEE,
            connect_action=UpdateConnectionAction.DISCONNECT,
            user_id=invitee.username,
        )
        assert response_non_member.data is None
        assert response_non_member.errors is not None

        # THEN anonymous user withdraws invite of invitee (error)
        response_anonymous = mutate_update_space_user_connection_raw(
            auth_user=AnonymousUser,
            space_id=space.id,
            connection_type=SpaceUserConnectionType.MEMBERSHIP_INVITEE,
            connect_action=UpdateConnectionAction.DISCONNECT,
            user_id=invitee.username,
        )
        assert response_anonymous.data is None
        assert response_anonymous.errors is not None

        # THEN Invited user still has invitee status
        assert get_space_for_user(invitee, space)["connectionStatusToMyself"] == [
            SpaceUserConnectionType.MEMBERSHIP_INVITEE.value
        ]

    @mock.patch("openbook_communities.schema.mutations.invalidate_discover_spaces_query_cache")
    def test_space_admin_grant_and_revoke_admin_access_success(self, mock_invalidate_discover_spaces_query_cache):
        space_member = make_user()
        space_creator = make_user()
        space = make_community(creator=space_creator)
        space.add_member(space_member)

        def member_result(user, is_admin):
            return {
                "user": {"id": user.username},
                "isAdministrator": is_admin,
            }

        # Admin user grants admin privileges to a member user
        response = mutate_update_space_user_connection_data(
            auth_user=space_creator,
            space_id=space.id,
            connection_type=SpaceUserConnectionType.ADMINISTRATOR,
            connect_action=UpdateConnectionAction.GRANT_ADMIN_ACCESS,
            user_id=space_member.username,
        )

        assert_paged_results_equal(
            response["members"],
            [member_result(space_creator, is_admin=True), member_result(space_member, is_admin=True)],
        )

        CommunityAdminPrivilegesGrantedNotification = get_community_admin_privileges_granted_notification_model()
        community_admin_privileges_granted_notifications = CommunityAdminPrivilegesGrantedNotification.objects.filter(
            granted_user=space_member
        )
        assert len(community_admin_privileges_granted_notifications) == 1
        notification = community_admin_privileges_granted_notifications.first()
        assert notification.community == space
        assert notification.notification.first().notification_type == "CAPG"

        # Admin user revokes admin privileges to an admin user
        response = mutate_update_space_user_connection_data(
            auth_user=space_creator,
            space_id=space.id,
            connection_type=SpaceUserConnectionType.ADMINISTRATOR,
            connect_action=UpdateConnectionAction.REVOKE_ADMIN_ACCESS,
            user_id=space_member.username,
        )

        assert_paged_results_equal(
            response["members"],
            [member_result(space_creator, is_admin=True), member_result(space_member, is_admin=False)],
        )

        CommunityAdminPrivilegesRevokedNotification = get_community_admin_privileges_revoked_notification_model()
        community_admin_privileges_revoked_notifications = CommunityAdminPrivilegesRevokedNotification.objects.filter(
            revoked_user=space_member
        )
        assert len(community_admin_privileges_revoked_notifications) == 1
        notification = community_admin_privileges_revoked_notifications.first()
        assert notification.community == space
        assert notification.notification.first().notification_type == "CAPR"

        mock_invalidate_discover_spaces_query_cache.assert_called()

    @mock.patch("openbook_notifications.services.NotificationsService.send_space_membership_request_notification")
    @mock.patch("openbook_notifications.services.NotificationsService.send_space_membership_invite_notification")
    @mock.patch("openbook_communities.schema.mutations.invalidate_discover_spaces_query_cache")
    @mock.patch("openbook_notifications.api.NotificationApi.cancel_workflow")
    @mock.patch("openbook_notifications.api.NotificationApi.delete_in_app_messages")
    def test_revoking_space_admin_access_deletes_pending_notifications(
        self,
        mock_notification_api_delete_in_app_messages,
        mock_notification_api_cancel_workflow,
        mock_invalidate_discover_spaces_query_cache,
        mock_send_space_membership_invite_notification,
        mock_send_space_membership_request_notification,
    ):
        admin = make_user()
        other_admin = make_user()
        invitee = make_user()
        membership_requestor = make_user()

        space = make_community(admins=[admin, other_admin])

        # Invite invitee to join space
        mutate_update_space_user_connection_data(
            auth_user=admin,
            space_id=space.id,
            user_id=invitee.id,
            connection_type=SpaceUserConnectionType.MEMBERSHIP_INVITEE,
            connect_action=UpdateConnectionAction.CONNECT,
        )
        invite = space.get_membership_invite(invitee)

        # Receive request from membership_requestor to join space
        mutate_update_space_user_connection_data(
            auth_user=membership_requestor,
            space_id=space.id,
            connection_type=SpaceUserConnectionType.MEMBERSHIP_REQUESTOR,
            connect_action=UpdateConnectionAction.CONNECT,
        )
        membership_request = space.get_membership_request(membership_requestor)

        # WHEN
        # Other admin revokes admin rights
        response = mutate_update_space_user_connection_raw(
            auth_user=other_admin,
            space_id=space.id,
            connection_type=SpaceUserConnectionType.ADMINISTRATOR,
            connect_action=UpdateConnectionAction.REVOKE_ADMIN_ACCESS,
            user_id=admin.username,
        )

        # THEN
        assert response.errors is None
        assert response.data is not None

        # Do not expect pending workflows to be cancelled, as there is still another admin
        mock_notification_api_cancel_workflow.assert_not_called()
        # Expect pending notifications for former admin to be deleted
        mock_notification_api_delete_in_app_messages.assert_has_calls(
            [
                mock.call(transaction_id=str(membership_request.id), subscriber_id=str(admin.username)),
                mock.call(transaction_id=str(invite.id), subscriber_id=str(admin.username)),
            ]
        )

    @mock.patch("openbook_communities.schema.mutations.invalidate_discover_spaces_query_cache")
    def test_space_admin_grant_and_revoke_admin_access_errors(self, mock_invalidate_discover_spaces_query_cache):
        space_member = make_user()
        space_creator = make_user()
        space_admin = make_user()
        external_user = make_user()
        space = make_community(creator=space_creator)
        space.add_member(space_member)
        space.add_member(space_admin)
        space.add_administrator(space_admin)

        # Admin user cannot grant admin privileges to an admin user
        response = mutate_update_space_user_connection_raw(
            auth_user=space_creator,
            space_id=space.id,
            connection_type=SpaceUserConnectionType.ADMINISTRATOR,
            connect_action=UpdateConnectionAction.GRANT_ADMIN_ACCESS,
            user_id=space_admin.username,
        )

        assert response.data is None
        assert response.errors is not None
        assert "User is already an administrator." in response.errors[0].extensions["errors"]
        assert (
            space.is_user_with_username_administrator_of_community_with_name(space_admin.username, space.name) is True
        )

        # Admin user cannot grant admin privileges to an external user
        response = mutate_update_space_user_connection_raw(
            auth_user=space_admin,
            space_id=space.id,
            connection_type=SpaceUserConnectionType.ADMINISTRATOR,
            connect_action=UpdateConnectionAction.GRANT_ADMIN_ACCESS,
            user_id=external_user.username,
        )

        assert response.data is None
        assert response.errors is not None
        assert (
            "Cannot make administrator a user that is not part of the space."
            in response.errors[0].extensions["errors"]
        )
        assert space.is_user_with_username_member_of_community_with_name(external_user.username, space.name) is False

        # Admin user cannot revoke admin privileges to a member user
        response = mutate_update_space_user_connection_raw(
            auth_user=space_admin,
            space_id=space.id,
            connection_type=SpaceUserConnectionType.ADMINISTRATOR,
            connect_action=UpdateConnectionAction.REVOKE_ADMIN_ACCESS,
            user_id=space_member.username,
        )

        assert response.data is None
        assert response.errors is not None
        assert "User to remove is not an administrator." in response.errors[0].extensions["errors"]
        assert (
            space.is_user_with_username_administrator_of_community_with_name(space_member.username, space.name)
            is False
        )

        mock_invalidate_discover_spaces_query_cache.assert_called()

    @mock.patch("openbook_communities.schema.mutations.invalidate_discover_spaces_query_cache")
    def test_space_member_grant_and_revoke_admin_access_errors(self, mock_invalidate_discover_spaces_query_cache):
        member_user = make_user()
        member_user_2 = make_user()
        space_creator = make_user()
        space = make_community(creator=space_creator)
        space.add_member(member_user)
        space.add_member(member_user_2)

        # Member user cannot grant admin privileges to a member user
        response = mutate_update_space_user_connection_raw(
            auth_user=member_user,
            space_id=space.id,
            connection_type=SpaceUserConnectionType.ADMINISTRATOR,
            connect_action=UpdateConnectionAction.GRANT_ADMIN_ACCESS,
            user_id=member_user_2.username,
        )

        assert response.data is None
        assert (
            "Only the administrators of the space can grant administrator privileges."
            in response.errors[0].extensions["errors"]
        )
        assert (
            space.is_user_with_username_administrator_of_community_with_name(member_user_2.username, space.name)
            is False
        )

        # Member user cannot revoke admin privileges to an admin user
        response = mutate_update_space_user_connection_raw(
            auth_user=member_user,
            space_id=space.id,
            connection_type=SpaceUserConnectionType.ADMINISTRATOR,
            connect_action=UpdateConnectionAction.REVOKE_ADMIN_ACCESS,
            user_id=space_creator.username,
        )

        assert response.data is None
        assert (
            "Only the administrators of the space can revoke administrator privileges."
            in response.errors[0].extensions["errors"]
        )
        assert (
            space.is_user_with_username_administrator_of_community_with_name(member_user_2.username, space.name)
            is False
        )

        mock_invalidate_discover_spaces_query_cache.assert_called()

    @mock.patch("openbook_communities.schema.mutations.invalidate_discover_spaces_query_cache")
    @mock.patch("openbook_communities.schema.mutations.publish_space_user_added_event")
    @mock.patch("openbook_notifications.services.NotificationsService.send_space_membership_invite_notification")
    @mock.patch("openbook_notifications.api.NotificationApi.cancel_workflow")
    @mock.patch("openbook_notifications.api.NotificationApi.delete_in_app_messages")
    @mock.patch(
        "openbook_notifications.services.NotificationsService.send_space_membership_invite_approval_user_notification"
    )
    @mock.patch(
        "openbook_notifications.services.NotificationsService.send_space_membership_invite_approval_admin_notification"
    )
    def test_space_invite_approval_process(
        self,
        mock_send_space_membership_invite_approval_admin_notification,
        mock_send_space_membership_invite_approval_user_notification,
        mock_notification_api_delete_in_app_messages,
        mock_notification_api_cancel_workflow,
        mock_send_space_membership_invite_notification,
        mock_publish_space_user_added_event,
        mock_invalidate_discover_spaces_query_cache,
    ):
        invitee_email = "test@test.com"
        invitee = make_user(email=invitee_email)
        space_creator = make_user()
        space = make_community(creator=space_creator)
        mock_publish_space_user_added_event.return_value = None

        def member_result(user, is_admin):
            return {
                "user": {"id": user.username},
                "isAdministrator": is_admin,
            }

        # Preconditions
        pre_join_space = get_space_for_user(invitee, space)
        assert pre_join_space["connectionStatusToMyself"] == []
        assert_paged_results_equal(pre_join_space["members"], [member_result(space_creator, is_admin=True)])

        data = get_notifications(invitee)
        assert data["totalResults"] == 0
        data = get_notifications(space_creator)
        assert data["totalResults"] == 0

        # Send Invite Request
        mutate_invite_user_by_email(
            auth_user=space_creator,
            email=invitee_email,
            space_id=space.id,
        )

        # Invitee received Invite notification
        invite_received_notification = get_notifications(invitee)["data"][0]
        assert invite_received_notification["notificationType"] == "CI"
        assert invite_received_notification["options"]["space"]["title"] == space.title
        assert invite_received_notification["options"]["user"]["fullName"] == space_creator.profile.full_name()

        # Invited user has invitee status
        assert get_space_for_user(invitee, space)["connectionStatusToMyself"] == [
            SpaceUserConnectionType.MEMBERSHIP_INVITEE.value
        ]

        # THEN an invite object should have been created
        community_invite = space.get_membership_invite(invitee)

        # THEN invitee should receive notification via Notifications system
        mock_send_space_membership_invite_notification.assert_called_once_with(
            inviter=space_creator,
            recipient=invitee,
            space=space,
            community_invite=community_invite,
        )

        # Accept Invite
        space_after_approval = mutate_update_space_user_connection_data(
            auth_user=invitee,
            space_id=space.id,
            connection_type=SpaceUserConnectionType.MEMBERSHIP_INVITEE,
            connect_action=UpdateConnectionAction.CONNECT,
        )

        assert_paged_results_equal(
            space_after_approval["members"],
            [member_result(space_creator, is_admin=True), member_result(invitee, is_admin=False)],
        )

        # User has correct connection status
        assert get_space_for_user(invitee, space)["connectionStatusToMyself"] == [
            SpaceUserConnectionType.FOLLOWER.value,
            SpaceUserConnectionType.MEMBER.value,
        ]

        # User has approval notification
        invitee_notifications = get_notifications(invitee)
        assert invitee_notifications["totalResults"] == 1
        assert invitee_notifications["data"][0]["notificationType"] == "CMRA"

        # Staff has approval notification
        staff_notifications = get_notifications(space_creator)
        assert staff_notifications["totalResults"] == 1
        assert staff_notifications["data"][0]["notificationType"] == "CMRA"
        assert staff_notifications["data"][0]["options"]["space"]["title"] == space.title
        assert staff_notifications["data"][0]["options"]["user"]["fullName"] == invitee.profile.full_name()

        # User added event was sent
        mock_publish_space_user_added_event.assert_called_once_with(username=invitee.username, community=space)

        # THEN invite workflow should be cancelled
        mock_notification_api_cancel_workflow.assert_called_once_with(transaction_id=str(community_invite.id))

        # THEN in-app messages should be deleted
        mock_notification_api_delete_in_app_messages.assert_called_once_with(transaction_id=str(community_invite.id))

        # THEN user should receive notification via Notificaitons system
        mock_send_space_membership_invite_approval_user_notification.assert_called_once_with(
            invitee=invitee,
            space=space,
        )

        # THEN staff should receive notification via Notifications system
        kwargs = mock_send_space_membership_invite_approval_admin_notification.call_args.kwargs
        expected_recipients = [space_creator.username]

        self.assertEqual([r.username for r in kwargs["recipients"]], expected_recipients)
        self.assertEqual(kwargs["invitee"], invitee)
        self.assertEqual(kwargs["space"], space)

        mock_invalidate_discover_spaces_query_cache.assert_called()

    @mock.patch("openbook_notifications.api.NotificationApi.cancel_workflow")
    @mock.patch("openbook_notifications.api.NotificationApi.delete_in_app_messages")
    def test_space_invite_approval_process_with_membership_request_from_same_invited_user(
        self,
        mock_notification_api_delete_in_app_messages,
        mock_notification_api_cancel_workflow,
    ):
        invitee_email = "test@test.com"
        invitee = make_user(email=invitee_email)
        space_creator = make_user()
        space = make_community(creator=space_creator)

        def member_result(user, is_admin):
            return {
                "user": {"id": user.username},
                "isAdministrator": is_admin,
            }

        # Send Invite Request
        mutate_invite_user_by_email(
            auth_user=space_creator,
            email=invitee_email,
            space_id=space.id,
        )

        # Invited user has invitee status
        assert get_space_for_user(invitee, space)["connectionStatusToMyself"] == [
            SpaceUserConnectionType.MEMBERSHIP_INVITEE.value
        ]

        # Create a Membership Request
        mutate_update_space_user_connection_data(
            auth_user=invitee,
            space_id=space.id,
            connection_type=SpaceUserConnectionType.MEMBERSHIP_REQUESTOR,
            connect_action=UpdateConnectionAction.CONNECT,
        )

        # THEN an invite object should have been created
        invite = space.get_membership_invite(invitee)

        # THEN an membership request object should have been created
        membership_request = space.get_membership_request(invitee)

        # Accept Invite
        space_after_approval = mutate_update_space_user_connection_data(
            auth_user=invitee,
            space_id=space.id,
            connection_type=SpaceUserConnectionType.MEMBERSHIP_INVITEE,
            connect_action=UpdateConnectionAction.CONNECT,
        )

        assert_paged_results_equal(
            space_after_approval["members"],
            [member_result(space_creator, is_admin=True), member_result(invitee, is_admin=False)],
        )

        # User has correct connection status (not including MEMBERSHIP_REQUESTOR)
        assert get_space_for_user(invitee, space)["connectionStatusToMyself"] == [
            SpaceUserConnectionType.FOLLOWER.value,
            SpaceUserConnectionType.MEMBER.value,
        ]

        # THEN invite and membership request workflows should be cancelled
        mock_notification_api_cancel_workflow.assert_has_calls(
            [mock.call(transaction_id=str(membership_request.id)), mock.call(transaction_id=str(invite.id))]
        )

        # THEN in-app messages should be deleted
        mock_notification_api_delete_in_app_messages.assert_has_calls(
            [
                mock.call(transaction_id=str(membership_request.id)),
                mock.call(
                    transaction_id=str(invite.id),
                ),
            ]
        )

    @mock.patch("openbook_communities.schema.mutations.invalidate_discover_spaces_query_cache")
    @mock.patch("openbook_communities.schema.mutations.publish_space_user_added_event")
    @mock.patch("openbook_notifications.services.NotificationsService.send_space_membership_invite_notification")
    @mock.patch("openbook_notifications.api.NotificationApi.cancel_workflow")
    @mock.patch("openbook_notifications.api.NotificationApi.delete_in_app_messages")
    @mock.patch(
        "openbook_notifications.services.NotificationsService.send_space_membership_invite_decline_user_notification"
    )
    @mock.patch(
        "openbook_notifications.services.NotificationsService.send_space_membership_invite_decline_admin_notification"
    )
    def test_space_invite_rejection_process(
        self,
        mock_send_space_membership_invite_decline_admin_notification,
        mock_send_space_membership_invite_decline_user_notification,
        mock_notification_api_delete_in_app_messages,
        mock_notification_api_cancel_workflow,
        mock_send_space_membership_invite_notification,
        mock_publish_space_user_added_event,
        mock_invalidate_discover_spaces_query_cache,
    ):
        invitee_email = "test@test.com"
        invitee = make_user(email=invitee_email)
        space_creator = make_user()
        space = make_community(creator=space_creator)
        mock_publish_space_user_added_event.return_value = None

        def member_result(user, is_admin):
            return {
                "user": {"id": user.username},
                "isAdministrator": is_admin,
            }

        # Preconditions
        pre_join_space = get_space_for_user(invitee, space)
        assert pre_join_space["connectionStatusToMyself"] == []
        assert_paged_results_equal(pre_join_space["members"], [member_result(space_creator, is_admin=True)])

        data = get_notifications(invitee)
        assert data["totalResults"] == 0
        data = get_notifications(space_creator)
        assert data["totalResults"] == 0

        # Send Invite Request
        mutate_invite_user_by_email(
            auth_user=space_creator,
            email=invitee_email,
            space_id=space.id,
        )

        # Invitee received Invite notification
        invite_received_notification = get_notifications(invitee)["data"][0]
        assert invite_received_notification["notificationType"] == "CI"
        assert invite_received_notification["options"]["space"]["title"] == space.title
        assert invite_received_notification["options"]["user"]["fullName"] == space_creator.profile.full_name()

        # Invited user has invitee status
        assert get_space_for_user(invitee, space)["connectionStatusToMyself"] == [
            SpaceUserConnectionType.MEMBERSHIP_INVITEE.value
        ]

        # THEN an invite object should have been created
        community_invite = space.get_membership_invite(invitee)

        # THEN invitee should receive notification via Notifications system
        mock_send_space_membership_invite_notification.assert_called_once_with(
            inviter=space_creator,
            recipient=invitee,
            space=space,
            community_invite=community_invite,
        )

        # Decline invite
        space_after_approval = mutate_update_space_user_connection_data(
            auth_user=invitee,
            space_id=space.id,
            connection_type=SpaceUserConnectionType.MEMBERSHIP_INVITEE,
            connect_action=UpdateConnectionAction.DISCONNECT,
        )

        assert_paged_results_equal(
            space_after_approval["members"],
            [member_result(space_creator, is_admin=True)],
        )

        # User has no connection status
        assert get_space_for_user(invitee, space)["connectionStatusToMyself"] == []

        # User has notification that they declined their invitation
        invitee_notifications = get_notifications(invitee)
        assert invitee_notifications["totalResults"] == 1
        assert invitee_notifications["data"][0]["notificationType"] == "CID"

        # Staff has notification that the invitee declined their invitation
        staff_notifications = get_notifications(space_creator)
        assert staff_notifications["totalResults"] == 1
        assert staff_notifications["data"][0]["notificationType"] == "CID"
        assert staff_notifications["data"][0]["options"]["space"]["title"] == space.title
        assert staff_notifications["data"][0]["options"]["user"]["fullName"] == invitee.profile.full_name()

        # THEN invite workflow should be cancelled
        mock_notification_api_cancel_workflow.assert_called_once_with(transaction_id=str(community_invite.id))

        # THEN in-app messages should be deleted
        mock_notification_api_delete_in_app_messages.assert_called_once_with(transaction_id=str(community_invite.id))

        # THEN user should receive notification via Notificaitons system
        mock_send_space_membership_invite_decline_user_notification.assert_called_once_with(
            invitee=invitee,
            space=space,
        )

        # THEN inviting staff member should receive notification via Notifications system
        mock_send_space_membership_invite_decline_admin_notification.assert_called_once_with(
            recipient=space.creator,
            invitee=invitee,
            space=space,
        )

        mock_invalidate_discover_spaces_query_cache.assert_called()

    @mock.patch("openbook_communities.schema.mutations.publish_space_user_left_event")
    def test_space_member_leaves_community_success(self, mock_publish_space_user_left_event):
        member_user = make_user()
        space_creator = make_user()

        space = make_community(creator=space_creator)
        space.add_member(member_user)

        CommunityNotificationsSubscription.enable_new_post_notification_for_community(
            community=space, subscriber=member_user
        )

        response = mutate_update_space_user_connection_raw(
            auth_user=member_user,
            space_id=space.id,
            connection_type=SpaceUserConnectionType.MEMBER,
            connect_action=UpdateConnectionAction.LEAVE_SPACE,
        )

        assert response.errors is None
        assert response.data is not None

        memberships = space.memberships.all()
        assert len(memberships) == 1
        assert member_user not in memberships
        assert not CommunityNotificationsSubscription.objects.filter(community=space, subscriber=member_user).exists()
        mock_publish_space_user_left_event.assert_called_once_with(user=member_user, community=space)

    @mock.patch("openbook_communities.schema.mutations.publish_space_user_left_event")
    def test_space_admin_leaves_community_success(self, mock_publish_space_user_left_event):
        space_creator = make_user()
        member_user_admin = make_user()

        space = make_community(creator=space_creator)
        space.add_member(member_user_admin)
        space.add_administrator(member_user_admin)

        CommunityNotificationsSubscription.enable_new_post_notification_for_community(
            community=space, subscriber=space_creator
        )

        response = mutate_update_space_user_connection_raw(
            auth_user=space_creator,
            space_id=space.id,
            connection_type=SpaceUserConnectionType.ADMINISTRATOR,
            connect_action=UpdateConnectionAction.LEAVE_SPACE,
        )

        assert response.errors is None
        assert response.data is not None

        memberships = space.memberships.all()
        assert len(memberships) == 1
        assert space_creator not in memberships
        assert not CommunityNotificationsSubscription.objects.filter(
            community=space, subscriber=space_creator
        ).exists()

        mock_publish_space_user_left_event.assert_called_once_with(user=space_creator, community=space)

    @mock.patch("openbook_notifications.services.NotificationsService.send_space_membership_request_notification")
    @mock.patch("openbook_notifications.services.NotificationsService.send_space_membership_invite_notification")
    @mock.patch("openbook_communities.schema.mutations.publish_space_user_left_event")
    @mock.patch("openbook_notifications.api.NotificationApi.cancel_workflow")
    @mock.patch("openbook_notifications.api.NotificationApi.delete_in_app_messages")
    def test_space_admin_leaves_community_deletes_pending_notifications(
        self,
        mock_notification_api_delete_in_app_messages,
        mock_notification_api_cancel_workflow,
        mock_publish_space_user_left_event,
        mock_send_space_membership_invite_notification,
        mock_send_space_membership_request_notification,
    ):
        admin = make_user()
        other_admin = make_user()
        invitee = make_user()
        membership_requestor = make_user()

        space = make_community(admins=[admin, other_admin])

        # Invite invitee to join space
        mutate_update_space_user_connection_data(
            auth_user=admin,
            space_id=space.id,
            user_id=invitee.id,
            connection_type=SpaceUserConnectionType.MEMBERSHIP_INVITEE,
            connect_action=UpdateConnectionAction.CONNECT,
        )
        invite = space.get_membership_invite(invitee)

        # Receive request from membership_requestor to join space
        mutate_update_space_user_connection_data(
            auth_user=membership_requestor,
            space_id=space.id,
            connection_type=SpaceUserConnectionType.MEMBERSHIP_REQUESTOR,
            connect_action=UpdateConnectionAction.CONNECT,
        )
        membership_request = space.get_membership_request(membership_requestor)

        # WHEN
        response = mutate_update_space_user_connection_raw(
            auth_user=admin,
            space_id=space.id,
            connection_type=SpaceUserConnectionType.ADMINISTRATOR,
            connect_action=UpdateConnectionAction.LEAVE_SPACE,
        )

        # THEN
        assert response.errors is None
        assert response.data is not None

        # Do not expect pending workflows to be cancelled, as there is still another admin
        mock_notification_api_cancel_workflow.assert_not_called()
        # Expect pending notifications for former admin to be deleted
        mock_notification_api_delete_in_app_messages.assert_has_calls(
            [
                mock.call(transaction_id=str(membership_request.id), subscriber_id=str(admin.username)),
                mock.call(transaction_id=str(invite.id), subscriber_id=str(admin.username)),
            ]
        )

    @mock.patch("openbook_communities.schema.mutations.publish_space_user_left_event")
    def test_space_member_leaves_community_error_only_member(self, mock_publish_space_user_left_event):
        space_creator = make_user()

        space = make_community(creator=space_creator)

        CommunityNotificationsSubscription.enable_new_post_notification_for_community(
            community=space, subscriber=space_creator
        )

        response = mutate_update_space_user_connection_raw(
            auth_user=space_creator,
            space_id=space.id,
            connection_type=SpaceUserConnectionType.MEMBER,
            connect_action=UpdateConnectionAction.LEAVE_SPACE,
        )

        assert response.errors is not None
        assert response.data is None
        assert "You cannot leave a community where you are the only member" in str(
            response.errors[0].extensions["errors"]
        )

        memberships = space.memberships.all()
        assert len(memberships) == 1
        assert CommunityNotificationsSubscription.objects.filter(community=space, subscriber=space_creator).exists()

        mock_publish_space_user_left_event.assert_not_called()

    @mock.patch("openbook_communities.schema.mutations.publish_space_user_left_event")
    def test_space_admin_leaves_community_error_only_admin(self, mock_publish_space_user_left_event):
        space_creator = make_user()
        member_user_admin = make_user()

        space = make_community(creator=space_creator)
        space.add_member(member_user_admin)

        CommunityNotificationsSubscription.enable_new_post_notification_for_community(
            community=space, subscriber=space_creator
        )

        response = mutate_update_space_user_connection_raw(
            auth_user=space_creator,
            space_id=space.id,
            connection_type=SpaceUserConnectionType.ADMINISTRATOR,
            connect_action=UpdateConnectionAction.LEAVE_SPACE,
        )

        assert response.errors is not None
        assert response.data is None
        assert "You cannot leave a community where you are the only admin" in str(
            response.errors[0].extensions["errors"]
        )

        memberships = space.memberships.all()
        assert len(memberships) == 2

        assert CommunityNotificationsSubscription.objects.filter(community=space, subscriber=space_creator).exists()

        mock_publish_space_user_left_event.assert_not_called()

    @mock.patch("openbook_communities.schema.mutations.publish_space_user_removed_event")
    def test_remove_member_from_community_success(self, mock_publish_space_user_removed_event):
        space_creator = make_user()
        member_user = make_user()

        space = make_community(creator=space_creator)
        space.add_member(member_user)

        CommunityNotificationsSubscription.enable_new_post_notification_for_community(
            community=space, subscriber=member_user
        )

        response = mutate_update_space_user_connection_raw(
            auth_user=space_creator,
            space_id=space.id,
            connection_type=SpaceUserConnectionType.ADMINISTRATOR,
            connect_action=UpdateConnectionAction.REMOVE_MEMBER,
            user_id=member_user.username,
        )

        assert response.errors is None
        assert response.data is not None

        memberships = space.memberships.all().values_list("user__id", flat=True)
        assert len(memberships) == 1
        assert member_user not in memberships

        assert not CommunityNotificationsSubscription.objects.filter(community=space, subscriber=member_user).exists()
        CommunityMembershipRevokedNotification = get_community_membership_revoked_notification_model()
        community_membership_revoked_notifications = CommunityMembershipRevokedNotification.objects.filter(
            revoked_user=member_user
        )
        assert len(community_membership_revoked_notifications) == 1
        notification = community_membership_revoked_notifications.first()
        assert notification.community == space
        assert notification.notification.first().notification_type == "CMRE"

        mock_publish_space_user_removed_event.assert_called_once_with(user=member_user, community=space)

    @mock.patch("openbook_notifications.services.NotificationsService.send_space_membership_request_notification")
    @mock.patch("openbook_notifications.services.NotificationsService.send_space_membership_invite_notification")
    @mock.patch("openbook_communities.schema.mutations.publish_space_user_left_event")
    @mock.patch("openbook_notifications.api.NotificationApi.cancel_workflow")
    @mock.patch("openbook_notifications.api.NotificationApi.delete_in_app_messages")
    def test_remove_member_from_community_deletes_pending_notifications(
        self,
        mock_notification_api_delete_in_app_messages,
        mock_notification_api_cancel_workflow,
        mock_publish_space_user_left_event,
        mock_send_space_membership_invite_notification,
        mock_send_space_membership_request_notification,
    ):
        admin = make_user()
        other_admin = make_user()
        invitee = make_user()
        membership_requestor = make_user()

        space = make_community(admins=[admin, other_admin])

        # Invite invitee to join space
        mutate_update_space_user_connection_data(
            auth_user=admin,
            space_id=space.id,
            user_id=invitee.id,
            connection_type=SpaceUserConnectionType.MEMBERSHIP_INVITEE,
            connect_action=UpdateConnectionAction.CONNECT,
        )
        invite = space.get_membership_invite(invitee)

        # Receive request from membership_requestor to join space
        mutate_update_space_user_connection_data(
            auth_user=membership_requestor,
            space_id=space.id,
            connection_type=SpaceUserConnectionType.MEMBERSHIP_REQUESTOR,
            connect_action=UpdateConnectionAction.CONNECT,
        )
        membership_request = space.get_membership_request(membership_requestor)

        # WHEN
        # Other admin removes admin from space
        response = mutate_update_space_user_connection_raw(
            auth_user=other_admin,
            space_id=space.id,
            connection_type=SpaceUserConnectionType.ADMINISTRATOR,
            connect_action=UpdateConnectionAction.REMOVE_MEMBER,
            user_id=admin.username,
        )

        # THEN
        assert response.errors is None
        assert response.data is not None

        # Do not expect pending workflows to be cancelled, as there is still another admin
        mock_notification_api_cancel_workflow.assert_not_called()
        # Expect pending notifications for former admin to be deleted
        mock_notification_api_delete_in_app_messages.assert_has_calls(
            [
                mock.call(transaction_id=str(membership_request.id), subscriber_id=str(admin.username)),
                mock.call(transaction_id=str(invite.id), subscriber_id=str(admin.username)),
            ]
        )

    @mock.patch("openbook_communities.schema.mutations.publish_space_user_removed_event")
    def test_remove_member_from_community_error_only_admin(self, mock_publish_space_user_removed_event):
        space_creator = make_user()
        member_user = make_user()
        request_user = make_user()

        space = make_community(creator=space_creator)
        space.add_member(member_user)
        space.add_member(request_user)

        CommunityNotificationsSubscription.enable_new_post_notification_for_community(
            community=space, subscriber=member_user
        )

        response = mutate_update_space_user_connection_raw(
            auth_user=request_user,
            space_id=space.id,
            connection_type=SpaceUserConnectionType.ADMINISTRATOR,
            connect_action=UpdateConnectionAction.REMOVE_MEMBER,
            user_id=member_user.username,
        )

        assert response.errors is not None
        assert response.data is None

        assert "Only the administrators of the space can remove members" in str(
            response.errors[0].extensions["errors"]
        )

        memberships = space.memberships.all().values_list("user__id", flat=True)
        assert len(memberships) == 3
        assert member_user.id in memberships
        assert CommunityNotificationsSubscription.objects.filter(community=space, subscriber=member_user).exists()

        CommunityMembershipRevokedNotification = get_community_membership_revoked_notification_model()
        community_membership_revoked_notifications = CommunityMembershipRevokedNotification.objects.filter(
            revoked_user=member_user
        )
        assert len(community_membership_revoked_notifications) == 0

        mock_publish_space_user_removed_event.assert_not_called()

    def test_space_with_posts(self):
        user_member = make_user()
        user_external = make_user()
        space = make_community(creator=user_member)

        public_posts = [
            user_member.create_post(text=make_fake_post_text(), title=make_fake_post_title(), is_public=True)
            for _ in range(5)
        ]
        for post in public_posts:
            post.community = space
            post.save()
        public_ids = [str(post.id) for post in public_posts]

        private_posts = [
            user_member.create_community_post(
                space.id,
                text=make_fake_post_text(),
                title=make_fake_post_title(),
                visibility=VisibilityType.MEMBERS.value,
            )
            for _ in range(3)
        ]
        for post in private_posts:
            post.community = space
            post.save()
        private_ids = [str(post.id) for post in private_posts]

        # member user with visibility all shows all posts
        data = get_space_by_id_with_posts(user_member, space.id, VisibilityFilter.ALL)
        posts_data = data["posts"]["data"]
        assert data["id"] == str(space.id)
        assert data["hasPublicPosts"] is True
        assert data["hasPrivatePosts"] is True
        assert data["posts"]["totalResults"] == len(public_posts) + len(private_posts)
        assert len(private_post_ids(posts_data)) == len(private_ids)
        assert len(public_post_ids(posts_data)) == len(public_ids)
        assert posts_data[0]["created"] >= posts_data[1]["created"]

        # member user with visibility public posts shows only public posts
        data = get_space_by_id_with_posts(user_member, space.id, VisibilityFilter.PUBLIC)
        posts_data = data["posts"]["data"]
        assert data["id"] == str(space.id)
        assert data["posts"]["totalResults"] == len(public_posts)
        assert len(public_post_ids(posts_data)) == len(public_ids)
        assert len(private_post_ids(posts_data)) == 0
        assert posts_data[0]["created"] >= posts_data[1]["created"]

        # member user with visibility private posts shows only private posts
        data = get_space_by_id_with_posts(user_member, space.id, VisibilityFilter.MEMBERS)
        posts_data = data["posts"]["data"]
        assert data["id"] == str(space.id)
        assert data["posts"]["totalResults"] == len(private_posts)
        assert len(public_post_ids(posts_data)) == 0
        assert len(private_post_ids(posts_data)) == len(private_ids)
        assert posts_data[0]["created"] >= posts_data[1]["created"]

        # external user without visibility filter shows public posts
        data = get_space_by_id_with_posts(user_external, space.id)
        posts_data = data["posts"]["data"]
        assert data["id"] == str(space.id)
        assert data["posts"]["totalResults"] == len(public_posts)
        assert len(public_post_ids(posts_data)) == len(public_ids)
        assert len(private_post_ids(posts_data)) == 0
        assert posts_data[0]["created"] >= posts_data[1]["created"]

        # external user visibility filter is ignored and shows public posts
        data = get_space_by_id_with_posts(user_external, space.id, VisibilityFilter.MEMBERS)
        posts_data = data["posts"]["data"]
        assert data["id"] == str(space.id)
        assert data["posts"]["totalResults"] == len(public_posts)
        assert len(public_post_ids(posts_data)) == len(public_ids)
        assert len(private_post_ids(posts_data)) == 0
        assert posts_data[0]["created"] >= posts_data[1]["created"]

    def test_space_with_sorted_members(self):
        # Create space and members
        admin1 = make_user(name="Xenia", last_name="Admin")
        admin2 = make_user(name="John", last_name="Admin")
        user1 = make_user(name="Angela", last_name="User")
        user2 = make_user(name="Angela", last_name="Member")
        user3 = make_user(name="Another", last_name="User")
        space = make_community(creator=admin1)
        space.add_member(admin2)
        space.add_administrator(admin2)
        space.add_member(user1)
        space.add_member(user2)
        space.add_member(user3)

        response = async_to_sync(schema.execute)(
            """
            query($id:String!) {
                spaceById(idOrName:$id) {
                    members {
                        totalResults
                        data {
                            user {
                                fullName
                            }
                        }
                    }
                }
            }
            """,
            variable_values={"id": str(space.id)},
            context_value=benedict({"request": {"user": AnonymousUser}}),
        )

        # Check sort order of members: First by membership (admins before members), then by full name
        assert response.errors is None
        paged_members = response.data["spaceById"]["members"]
        assert paged_members["totalResults"] == 5
        members = paged_members["data"]
        assert members[0]["user"]["fullName"] == "John Admin"
        assert members[1]["user"]["fullName"] == "Xenia Admin"
        assert members[2]["user"]["fullName"] == "Angela Member"
        assert members[3]["user"]["fullName"] == "Angela User"
        assert members[4]["user"]["fullName"] == "Another User"

    @mock.patch("openbook_communities.schema.mutations.invalidate_discover_spaces_query_cache")
    def test_can_not_update_space_if_not_admin(self, mock_invalidate_discover_spaces_query_cache):
        user = make_user()
        community = make_community()
        update_space_mutation = """
            mutation test($input: UpdateSpaceInput!) {
                updateSpace(input: $input) {
                    id
                }
            }
            """

        response = async_to_sync(schema.execute)(
            update_space_mutation,
            context_value=benedict({"request": {"user": user}}),
            variable_values={"input": {"id": str(community.id), "title": "new title"}},
        )

        assert response.data is None
        assert "Can't update a community that you do not administrate." in str(response.errors[0].extensions["errors"])

        mock_invalidate_discover_spaces_query_cache.assert_not_called()

    @mock.patch("openbook_communities.schema.mutations.invalidate_discover_spaces_query_cache")
    def test_can_not_update_space_if_not_logged_in(self, mock_invalidate_discover_spaces_query_cache):
        community = make_community()
        update_space_mutation = """
            mutation test($input: UpdateSpaceInput!) {
                updateSpace(input: $input) {
                    id
                }
            }
            """

        response = async_to_sync(schema.execute)(
            update_space_mutation,
            variable_values={"input": {"id": str(community.id), "title": "new title"}},
            context_value=benedict({"request": {"user": AnonymousUser}}),
        )

        assert_is_unauthorized(response)
        mock_invalidate_discover_spaces_query_cache.assert_not_called()

    @mock.patch("openbook_communities.schema.mutations.publish_space_deleted_event")
    @mock.patch("openbook_communities.schema.mutations.invalidate_discover_spaces_query_cache")
    def test_can_not_delete_space_if_not_admin(
        self, mock_invalidate_discover_spaces_query_cache, mock_publish_space_deleted_event
    ):
        user = make_user()
        community = make_community()
        delete_space_mutation = """
            mutation test($id: UUID!) {
                deleteSpace(id: $id) {
                    success
                }
            }
            """

        response = async_to_sync(schema.execute)(
            delete_space_mutation,
            context_value=benedict({"request": {"user": user}}),
            variable_values={"id": str(community.id)},
        )

        assert response.data is None
        assert "Can't delete a community that you do not administrate." in str(response.errors[0].extensions["errors"])

        mock_invalidate_discover_spaces_query_cache.assert_not_called()
        mock_publish_space_deleted_event.assert_not_called()

    @mock.patch("openbook_communities.schema.mutations.publish_space_deleted_event")
    @mock.patch("openbook_communities.schema.mutations.invalidate_discover_spaces_query_cache")
    def test_can_not_delete_space_if_not_logged_in(
        self, mock_invalidate_discover_spaces_query_cache, mock_publish_space_deleted_event
    ):
        community = make_community()
        delete_space_mutation = """
            mutation test($id: UUID!) {
                deleteSpace(id: $id) {
                    success
                }
            }
            """

        response = async_to_sync(schema.execute)(
            delete_space_mutation,
            variable_values={"id": str(community.id)},
            context_value=benedict({"request": {"user": AnonymousUser}}),
        )

        assert_is_unauthorized(response)
        mock_invalidate_discover_spaces_query_cache.assert_not_called()
        mock_publish_space_deleted_event.assert_not_called()

    @mock.patch("openbook_communities.schema.mutations.publish_task_deleted_event")
    @mock.patch("openbook_communities.schema.mutations.publish_space_deleted_event")
    @mock.patch("openbook_communities.schema.mutations.invalidate_discover_spaces_query_cache")
    def test_can_delete_space(
        self,
        mock_invalidate_discover_spaces_query_cache,
        mock_publish_space_deleted_event,
        mock_publish_task_deleted_event,
    ):
        user = make_user()
        community = make_community(creator=user)
        task1 = make_community_task(community)
        make_community_task(community, is_deleted=True)
        task3 = make_community_task(community)
        # Creating task in other space to ensure no other tasks are deleted
        community2 = make_community(creator=user)
        make_community_task(community2)

        delete_space_mutation = """
            mutation test($id: UUID!) {
                deleteSpace(id: $id) {
                    success
                }
            }
            """

        response = async_to_sync(schema.execute)(
            delete_space_mutation,
            variable_values={"id": str(community.id)},
            context_value=benedict({"request": {"user": user}}),
        )

        assert response.errors is None
        assert response.data["deleteSpace"]["success"] is True

        mock_invalidate_discover_spaces_query_cache.assert_called_once()
        mock_publish_space_deleted_event.assert_called_once_with(community)
        assert mock_publish_task_deleted_event.call_count == 2
        mock_publish_task_deleted_event.assert_has_calls(
            [
                call(user, task1),
                call(user, task3),
            ]
        )

    @mock.patch("openbook_notifications.services.NotificationsService.send_space_membership_request_notification")
    @mock.patch("openbook_notifications.services.NotificationsService.send_space_membership_invite_notification")
    @mock.patch("openbook_communities.schema.mutations.publish_space_deleted_event")
    @mock.patch("openbook_communities.schema.mutations.invalidate_discover_spaces_query_cache")
    @mock.patch("openbook_notifications.api.NotificationApi.cancel_workflow")
    @mock.patch("openbook_notifications.api.NotificationApi.delete_in_app_messages")
    def test_can_delete_space_with_pending_notifications(
        self,
        mock_notification_api_delete_in_app_messages,
        mock_notification_api_cancel_workflow,
        mock_invalidate_discover_spaces_query_cache,
        mock_publish_space_deleted_event,
        mock_send_space_membership_invite_notification,
        mock_send_space_membership_request_notification,
    ):
        user = make_user()
        invitee = make_user()
        membership_requestor = make_user()
        community = make_community(creator=user)

        # Invite invitee to join space
        mutate_update_space_user_connection_data(
            auth_user=user,
            space_id=community.id,
            user_id=invitee.id,
            connection_type=SpaceUserConnectionType.MEMBERSHIP_INVITEE,
            connect_action=UpdateConnectionAction.CONNECT,
        )
        invite = community.get_membership_invite(invitee)

        # Receive request from membership_requestor to join space
        mutate_update_space_user_connection_data(
            auth_user=membership_requestor,
            space_id=community.id,
            connection_type=SpaceUserConnectionType.MEMBERSHIP_REQUESTOR,
            connect_action=UpdateConnectionAction.CONNECT,
        )
        membership_request = community.get_membership_request(membership_requestor)

        delete_space_mutation = """
            mutation test($id: UUID!) {
                deleteSpace(id: $id) {
                    success
                }
            }
            """

        response = async_to_sync(schema.execute)(
            delete_space_mutation,
            variable_values={"id": str(community.id)},
            context_value=benedict({"request": {"user": user}}),
        )

        assert response.errors is None
        assert response.data["deleteSpace"]["success"] is True

        # Expect pending notifications for invitations and membership requests to be deleted resp. workflows to be cancelled
        mock_notification_api_cancel_workflow.assert_has_calls(
            [mock.call(transaction_id=str(membership_request.id)), mock.call(transaction_id=str(invite.id))]
        )
        mock_notification_api_delete_in_app_messages.assert_has_calls(
            [mock.call(transaction_id=str(membership_request.id)), mock.call(transaction_id=str(invite.id))]
        )

    @mock.patch("openbook_communities.schema.mutations.publish_space_deleted_event")
    @mock.patch("openbook_communities.schema.mutations.invalidate_discover_spaces_query_cache")
    def test_delete_space_that_does_not_exist_passes(
        self, mock_invalidate_discover_spaces_query_cache, mock_publish_space_deleted_event
    ):
        user = make_user()

        delete_space_mutation = """
            mutation test($id: UUID!) {
                deleteSpace(id: $id) {
                    success
                }
            }
            """

        response = async_to_sync(schema.execute)(
            delete_space_mutation,
            variable_values={"id": "00000000-0000-0000-0000-ffffffffffff"},
            context_value=benedict({"request": {"user": user}}),
        )

        assert response.errors is None
        assert response.data["deleteSpace"]["success"] is True

        mock_invalidate_discover_spaces_query_cache.assert_not_called()
        mock_publish_space_deleted_event.assert_not_called()

    def test_spaces_missing_required_fields_do_not_pass_validation(self):
        user = make_user()

        validate_space_mutation = """
            mutation test($input: ValidateSpaceInput!) {
                validateSpace(input: $input) {
                    success
                }
            }
            """

        response = async_to_sync(schema.execute)(
            validate_space_mutation,
            context_value=benedict({"request": {"user": user}}),
            variable_values={"input": {}},
        )

        field_errors = json.loads(str(response.errors[0].extensions["errors"]))
        assert "required" == field_errors["title"][0]["code"]
        assert "required" == field_errors["description"][0]["code"]
        assert response.data is None

    def test_invalid_spaces_do_not_pass_validation(self):
        user = make_user()
        topics_v2 = make_topics_v2(7)
        empty_image = SimpleUploadedFile(name="cover.jpg", content="")

        validate_space_mutation = """
            mutation test($input: ValidateSpaceInput!) {
                validateSpace(input: $input) {
                    success
                }
            }
            """
        valid_input = {"title": "valid", "description": "valid"}

        expectedErrors = [
            {"field": "title", "value": None, "expected_code": "null"},
            {"field": "title", "value": "", "expected_code": "blank"},
            {"field": "title", "value": "  ", "expected_code": "blank"},
            {"field": "title", "value": "f", "expected_code": "min_length"},
            {"field": "title", "value": "f" * (COMMUNITY_TITLE_MAX_LENGTH + 1), "expected_code": "max_length"},
            {"field": "description", "value": None, "expected_code": "null"},
            {"field": "description", "value": "", "expected_code": "blank"},
            {
                "field": "description",
                "value": "f" * (COMMUNITY_DESCRIPTION_MAX_LENGTH + 1),
                "expected_code": "max_length",
            },
            {"field": "topicsV2", "value": None, "expected_code": "null"},
            {"field": "topicsV2", "value": [], "expected_code": "min_length"},
            {"field": "topicsV2", "value": topics_v2, "expected_code": "max_length"},
            {
                "field": "topicsV2",
                "value": ["unknown"],
                "expected_error": "TopicV2 'unknown' does not exist.",
            },
            {"field": "cover", "value": None, "expected_code": "null"},
            {"field": "cover", "value": {}, "expected_code": "invalid"},
            {"field": "cover", "value": "", "expected_code": "invalid"},
            {"field": "cover", "value": "foobar", "expected_code": "invalid"},
            {"field": "cover", "value": empty_image, "expected_code": "empty"},
            {"field": "cover", "value": create_large_image_file(), "expected_code": "max_upload_size"},
            {"field": "cover", "value": create_video_file(), "expected_code": "invalid_image"},
        ]

        for testCase in expectedErrors:
            response = async_to_sync(schema.execute)(
                validate_space_mutation,
                context_value=benedict({"request": {"user": user}}),
                variable_values={"input": valid_input | {testCase["field"]: testCase["value"]}},
            )

            assert (response.errors, testCase) is not None, "Expected error"
            if "expected_code" in testCase:
                field_errors = json.loads(response.errors[0].extensions["errors"])
                actual_code = field_errors[testCase["field"]][0]["code"]
                assert testCase["expected_code"] == actual_code, (
                    f"Expected error code {testCase['expected_code']} but got {actual_code} for input {testCase}"
                )
            else:
                assert testCase["expected_error"] in str(response.errors[0].message), (
                    f"Expected error {testCase['expected_error']} but got {str(response.errors[0].message)} for input {testCase}"
                )
            assert response.data is None

    def test_valid_partial_spaces_pass_validation(self):
        user = make_user()
        valid_input = {"title": "valid", "description": "valid"}
        topics_v2 = make_topics_v2(2)
        cover = SimpleUploadedFile(name="cover.jpg", content=simple_jpeg_bytes)
        location = "Hamburg, Germany"
        validate_space_mutation = """
            mutation test($input: ValidateSpaceInput!) {
                validateSpace(input: $input) {
                    success
                }
            }
            """

        valid_inputs = [
            valid_input,
            valid_input | {"cover": cover},
            valid_input | {"location": location},
            valid_input | {"topicsV2": topics_v2},
            valid_input | {"topicsV2": topics_v2, "cover": cover},
        ]

        for input in valid_inputs:
            response = async_to_sync(schema.execute)(
                validate_space_mutation,
                context_value=benedict({"request": {"user": user}}),
                variable_values={"input": input},
            )

            assert response.data["validateSpace"]["success"] is True
            assert response.errors is None

    def test_can_not_validate_space_if_not_logged_in(self):
        validate_space_mutation = """
            mutation test($input: ValidateSpaceInput!) {
                validateSpace(input: $input) {
                    success
                }
            }
            """
        valid_input = {"title": "valid", "description": "valid"}

        response = async_to_sync(schema.execute)(
            validate_space_mutation,
            variable_values={"input": valid_input},
            context_value=benedict({"request": {"user": AnonymousUser}}),
        )

        assert_is_unauthorized(response)

    @mock.patch("openbook_communities.schema.mutations.invalidate_discover_spaces_query_cache")
    @mock.patch("openbook_communities.schema.mutations.publish_space_created_event")
    def test_can_not_create_spaces_missing_required_fields(
        self, mock_publish_space_created_event, mock_invalidate_discover_spaces_query_cache
    ):
        user = make_user()
        valid_topics_v2 = make_topics_v2(2)
        valid_image = SimpleUploadedFile(name="cover.jpg", content=simple_jpeg_bytes)

        create_space_mutation = """
            mutation test($input: CreateSpaceInput!) {
                createSpace(input: $input) {
                    id
                }
            }
            """

        expectedErrors = [
            {
                "input": {"title": "valid", "description": "valid", "topicsV2": valid_topics_v2},
                "expected_error": "was not provided",
            },
            {
                "input": {"title": "valid", "topicsV2": valid_topics_v2, "cover": valid_image},
                "expected_error": "was not provided",
            },
            {
                "input": {"description": "valid", "topicsV2": valid_topics_v2, "cover": valid_image},
                "expected_error": "was not provided",
            },
            {
                "input": {"description": "valid", "topicsV2": valid_topics_v2, "cover": valid_image},
                "expected_error": "was not provided",
            },
        ]

        for testCase in expectedErrors:
            response = async_to_sync(schema.execute)(
                create_space_mutation,
                context_value=benedict({"request": {"user": user}}),
                variable_values={"input": testCase["input"]},
            )

            assert testCase["expected_error"] in str(response.errors[0].message)
            assert (response.data["createSpace"] if response.data else response.data) is None

        mock_publish_space_created_event.assert_not_called()
        mock_invalidate_discover_spaces_query_cache.assert_not_called()

    def test_validates_space_before_creation(self):
        user = make_user()
        topics_v2 = make_topics_v2(7)
        valid_topics_v2 = topics_v2[:2]
        valid_image = SimpleUploadedFile(name="cover.jpg", content=simple_jpeg_bytes)
        empty_image = SimpleUploadedFile(name="cover.jpg", content="")

        create_space_mutation = """
            mutation test($input: CreateSpaceInput!) {
                createSpace(input: $input) {
                    id
                }
            }
            """
        valid_input = {"title": "valid", "description": "valid", "topicsV2": valid_topics_v2, "cover": valid_image}

        expectedErrors = [
            {"field": "title", "value": None, "expected_error": "Expected non-nullable type"},
            {"field": "title", "value": "", "expected_code": "blank"},
            {"field": "title", "value": "f", "expected_code": "min_length"},
            {"field": "title", "value": "f" * (COMMUNITY_TITLE_MAX_LENGTH + 1), "expected_code": "max_length"},
            {"field": "description", "value": None, "expected_error": "Expected non-nullable type"},
            {"field": "description", "value": "", "expected_code": "blank"},
            {
                "field": "description",
                "value": "f" * (COMMUNITY_DESCRIPTION_MAX_LENGTH + 1),
                "expected_code": "max_length",
            },
            {"field": "topicsV2", "value": [], "expected_code": "min_length"},
            {"field": "topicsV2", "value": topics_v2, "expected_code": "max_length"},
            {
                "field": "topicsV2",
                "value": ["unknown"],
                "expected_error": "TopicV2 'unknown' does not exist.",
            },
            {"field": "cover", "value": None, "expected_error": "Expected non-nullable type"},
            {"field": "cover", "value": {}, "expected_code": "invalid"},
            {"field": "cover", "value": "", "expected_code": "invalid"},
            {"field": "cover", "value": "foobar", "expected_code": "invalid"},
            {"field": "cover", "value": empty_image, "expected_code": "empty"},
            {"field": "cover", "value": create_large_image_file(), "expected_code": "max_upload_size"},
            {"field": "cover", "value": create_video_file(), "expected_code": "invalid_image"},
        ]

        for testCase in expectedErrors:
            response = async_to_sync(schema.execute)(
                create_space_mutation,
                context_value=benedict({"request": {"user": user}}),
                variable_values={"input": valid_input | {testCase["field"]: testCase["value"]}},
            )

            if "expected_code" in testCase:
                field_errors = json.loads(response.errors[0].extensions["errors"])
                assert testCase["expected_code"] == field_errors[testCase["field"]][0]["code"]
            else:
                assert testCase["expected_error"] in str(response.errors[0].message)
            assert (response.data["createSpace"] if response.data else response.data) is None

    @mock.patch("openbook_communities.schema.mutations.invalidate_discover_spaces_query_cache")
    @mock.patch("openbook_communities.schema.mutations.publish_space_created_event")
    def test_can_create_space(self, mock_publish_space_created_event, mock_invalidate_discover_spaces_query_cache):
        user = make_user()
        topics_v2 = make_topics_v2(2)
        valid_image = SimpleUploadedFile(name="cover.jpg", content=simple_jpeg_bytes)

        create_space_mutation = """
            mutation test($input: CreateSpaceInput!) {
                createSpace(input: $input) {
                    id
                    name
                    title
                    description
                    topicsV2
                    cover
                    members {
                        data {
                            user {id}
                            isAdministrator
                        }
                    }
                }
            }
            """
        valid_input = {"title": "valid", "description": "valid", "topicsV2": topics_v2, "cover": valid_image}

        response = async_to_sync(schema.execute)(
            create_space_mutation,
            context_value=benedict({"request": {"user": user}}),
            variable_values={"input": valid_input},
        )

        assert response.errors is None

        created_space = response.data["createSpace"]
        assert "id" in created_space
        assert "valid" == created_space["name"]
        assert "valid" == created_space["title"]
        assert "valid" == created_space["description"]
        assert "cover.jpg" in created_space["cover"]
        assert topics_v2 == created_space["topicsV2"]

        # Verify that creator is admin
        assert 1 == len(created_space["members"]["data"])
        member = created_space["members"]["data"][0]
        assert str(user.username) == member["user"]["id"]
        assert member["isAdministrator"] is True

        community = Community.objects.get(id=created_space["id"])
        mock_publish_space_created_event.assert_called_once_with(community=community)
        mock_invalidate_discover_spaces_query_cache.assert_called_once()

    @mock.patch("openbook_communities.schema.mutations.invalidate_discover_spaces_query_cache")
    @mock.patch("openbook_communities.schema.mutations.publish_space_created_event")
    def test_can_create_space_with_topics_v2(
        self, mock_publish_space_created_event, mock_invalidate_discover_spaces_query_cache
    ):
        user = make_user()
        topics_v2 = make_topics_v2(2)
        valid_image = SimpleUploadedFile(name="cover.jpg", content=simple_jpeg_bytes)

        create_space_mutation = """
            mutation test($input: CreateSpaceInput!) {
                createSpace(input: $input) {
                    id
                    topicsV2
                }
            }
            """
        valid_input = {"title": "valid", "description": "valid", "topicsV2": topics_v2, "cover": valid_image}

        response = async_to_sync(schema.execute)(
            create_space_mutation,
            context_value=benedict({"request": {"user": user}}),
            variable_values={"input": valid_input},
        )

        assert response.errors is None

        created_space = response.data["createSpace"]
        assert sorted(topics_v2) == sorted(created_space["topicsV2"])

    @mock.patch("openbook_communities.schema.mutations.invalidate_discover_spaces_query_cache")
    @mock.patch("openbook_communities.schema.mutations.publish_space_created_event")
    def test_can_not_create_space_if_not_logged_in(
        self, mock_publish_space_created_event, mock_invalidate_discover_spaces_query_cache
    ):
        topics_v2 = make_topics_v2(7)
        valid_topics_v2 = topics_v2[:2]
        valid_image = SimpleUploadedFile(name="cover.jpg", content=simple_jpeg_bytes)

        create_space_mutation = """
            mutation test($input: CreateSpaceInput!) {
                createSpace(input: $input) {
                    id
                }
            }
            """
        valid_input = {"title": "valid", "description": "valid", "topicsV2": valid_topics_v2, "cover": valid_image}

        response = async_to_sync(schema.execute)(
            create_space_mutation,
            variable_values={"input": valid_input},
            context_value=benedict({"request": {"user": AnonymousUser}}),
        )

        assert_is_unauthorized(response)
        mock_publish_space_created_event.assert_not_called()
        mock_invalidate_discover_spaces_query_cache.assert_not_called()

    def test_validates_space_update(self):
        user = make_user()
        community = make_community()
        topics_v2 = make_topics_v2(7)
        empty_image = SimpleUploadedFile(name="cover.jpg", content="")

        update_space_mutation = """
            mutation test($input: UpdateSpaceInput!) {
                updateSpace(input: $input) {
                    id
                }
            }
            """
        base_input = {"id": str(community.id)}
        invalid_uuid = str(uuid4())

        expectedErrors = [
            {"field": "id", "value": None, "expected_error": "Expected non-nullable type"},
            {"field": "id", "value": invalid_uuid, "expected_error": "No community with the provided id exists."},
            {"field": "title", "value": "", "expected_code": "blank"},
            {"field": "title", "value": "f", "expected_code": "min_length"},
            {"field": "title", "value": "f" * (COMMUNITY_TITLE_MAX_LENGTH + 1), "expected_code": "max_length"},
            {"field": "description", "value": "", "expected_code": "blank"},
            {
                "field": "description",
                "value": "f" * (COMMUNITY_DESCRIPTION_MAX_LENGTH + 1),
                "expected_code": "max_length",
            },
            {"field": "topicsV2", "value": [], "expected_code": "min_length"},
            {"field": "topicsV2", "value": topics_v2, "expected_code": "max_length"},
            {
                "field": "topicsV2",
                "value": ["unknown"],
                "expected_error": "TopicV2 'unknown' does not exist",
            },
            {"field": "cover", "value": {}, "expected_code": "invalid"},
            {"field": "cover", "value": "", "expected_code": "invalid"},
            {"field": "cover", "value": "foobar", "expected_code": "invalid"},
            {"field": "cover", "value": empty_image, "expected_code": "empty"},
            {"field": "cover", "value": create_large_image_file(), "expected_code": "max_upload_size"},
            {"field": "cover", "value": create_video_file(), "expected_code": "invalid_image"},
            {"field": "avatar", "value": {}, "expected_code": "invalid"},
            {"field": "avatar", "value": "", "expected_code": "invalid"},
            {"field": "avatar", "value": "foobar", "expected_code": "invalid"},
            {"field": "avatar", "value": empty_image, "expected_code": "empty"},
            {"field": "avatar", "value": create_large_image_file(), "expected_code": "max_upload_size"},
            {"field": "avatar", "value": create_video_file(), "expected_code": "invalid_image"},
            {"field": "location", "value": None, "expected_code": "null"},
            {"field": "contactDescription", "value": "f" * 101, "expected_code": "max_length"},
            {"field": "contactPhone", "value": "9" * 101, "expected_code": "max_length"},
            {"field": "contactEmail", "value": "invalid", "expected_code": "invalid"},
            {
                "field": "onboardingSteps",
                "value": None,
                "expected_code": "null",
            },
            {
                "field": "onboardingSteps",
                "value": [{"text": None}],
                "expected_error": "Expected non-nullable type",
            },
            {
                "field": "onboardingSteps",
                "value": [{"text": "f" * 241}],
                "expected_code": "max_length",
                "error_path": "onboardingSteps.0.text",
            },
        ]

        for testCase in expectedErrors:
            response = async_to_sync(schema.execute)(
                update_space_mutation,
                context_value=benedict({"request": {"user": user}}),
                variable_values={
                    "input": base_input | {testCase["field"]: testCase["value"]},
                },
            )

            if "expected_code" in testCase:
                field_errors = json.loads(response.errors[0].extensions["errors"])
                error_path = testCase["error_path"] if "error_path" in testCase else testCase["field"]
                assert testCase["expected_code"] == benedict(field_errors)[error_path][0]["code"]

            else:
                assert testCase["expected_error"] in str(response.errors[0].message)
            assert (response.data["updateSpace"] if response.data else response.data) is None

    @mock.patch("openbook_communities.schema.mutations.invalidate_discover_spaces_query_cache")
    def test_can_not_update_space_without_passing_id(self, mock_invalidate_discover_spaces_query_cache):
        user = make_user()
        update_space_mutation = """
            mutation test($input: UpdateSpaceInput!) {
                updateSpace(input: $input) {
                    id
                }
            }
            """

        response = async_to_sync(schema.execute)(
            update_space_mutation,
            context_value=benedict({"request": {"user": user}}),
            variable_values={"input": {"title": "new title"}},
        )

        assert response.data is None
        assert "Field 'id' of required type 'UUID!' was not provided" in response.errors[0].message
        mock_invalidate_discover_spaces_query_cache.assert_not_called()

    @mock.patch("openbook_communities.schema.mutations.publish_task_updated_event")
    @mock.patch("openbook_communities.schema.mutations.publish_space_updated_event")
    @mock.patch("openbook_communities.schema.mutations.invalidate_discover_spaces_query_cache")
    def test_can_update_space(
        self,
        mock_invalidate_discover_spaces_query_cache,
        mock_publish_space_updated_event,
        mock_publish_task_updated_event,
    ):
        user = make_user()
        community = make_community(creator=user)
        task_1 = make_community_task(community)
        task_2 = make_community_task(community)
        topics_v2 = make_topics_v2(3)
        cover = SimpleUploadedFile(name="cover.jpg", content=simple_jpeg_bytes)
        cover2 = SimpleUploadedFile(name="cover2.jpg", content=simple_jpeg_bytes)
        avatar = SimpleUploadedFile(name="avatar.jpg", content=simple_jpeg_bytes)
        avatar2 = SimpleUploadedFile(name="avatar2.jpg", content=simple_jpeg_bytes)
        location = "Hamburg, Germany"
        update_space_mutation = """
            mutation test($input: UpdateSpaceInput!) {
                updateSpace(input: $input) {
                    id
                }
            }
            """
        base_input = {"id": str(community.id)}
        valid_inputs = [
            {"title": "new title"},
            {"description": "new description"},
            {"topicsV2": topics_v2[2:]},
            {"cover": cover},
            {"avatar": avatar},
            {
                "title": "newest title",
                "description": "newest description",
                "topicsV2": topics_v2[2:],
                "cover": cover2,
                "avatar": avatar2,
            },
            {"location": location},
            {"contactDescription": "Lorem ipsum"},
            {"contactPhone": "+49 123 12345"},
            {"contactEmail": "contact@space.com"},
            {"cover": None},
            {"avatar": None},
        ]

        for input in valid_inputs:
            response = async_to_sync(schema.execute)(
                update_space_mutation,
                context_value=benedict({"request": {"user": user}}),
                variable_values={"input": base_input | input},
            )

            assert str(community.id) == response.data["updateSpace"]["id"]
            assert response.errors is None

        assert mock_invalidate_discover_spaces_query_cache.call_count == len(valid_inputs)
        assert mock_publish_task_updated_event.call_count == len(valid_inputs) * 2  # two tasks associated to space
        for call_args in mock_publish_task_updated_event.call_args_list:
            assert call_args.kwargs["task"] == task_1 or call_args.kwargs["task"] == task_2
        assert mock_publish_space_updated_event.call_count == len(valid_inputs)
        for call_args in mock_publish_space_updated_event.call_args_list:
            assert call_args.kwargs["community"] == community

    def test_updated_space_has_new_values(self):
        user = make_user()
        community = make_community(creator=user)
        topics_v2 = make_topics_v2(2)

        cover = SimpleUploadedFile(name="cover.jpg", content=simple_jpeg_bytes)
        avatar = SimpleUploadedFile(name="avatar.jpg", content=simple_jpeg_bytes)
        blurhash_img = blurhash.encode(
            SimpleUploadedFile(name="blur.jpg", content=simple_jpeg_bytes), x_components=4, y_components=3
        )

        location = "Hamburg, Germany"
        update_space_mutation = """
            mutation test($input: UpdateSpaceInput!) {
                updateSpace(input: $input) {
                    id
                    title
                    description
                    topicsV2
                    cover
                    coverBlurhash
                    avatar
                    avatarBlurhash
                    location
                    contactDescription
                    contactPhone
                    contactEmail
                }
            }
            """
        input = {
            "id": str(community.id),
            "title": "newest title",
            "description": "newest description",
            "topicsV2": topics_v2,
            "cover": cover,
            "avatar": avatar,
            "location": location,
            "contactDescription": "Lorem ipsum",
            "contactPhone": "+49 123 12345",
            "contactEmail": "contact@space.com",
        }

        response = async_to_sync(schema.execute)(
            update_space_mutation,
            context_value=benedict({"request": {"user": user}}),
            variable_values={"input": input},
        )

        assert response.errors is None

        updated_space = response.data["updateSpace"]
        assert str(community.id) == updated_space["id"]
        assert "newest title" == updated_space["title"]
        assert "newest description" == updated_space["description"]
        assert sorted(updated_space["topicsV2"]) == sorted(topics_v2)
        assert "cover.jpg" in updated_space["cover"]
        assert "avatar.jpg" in updated_space["avatar"]
        assert blurhash_img == updated_space["coverBlurhash"]
        assert blurhash_img == updated_space["avatarBlurhash"]
        assert "Hamburg, Germany" == updated_space["location"]
        assert "Lorem ipsum" == updated_space["contactDescription"]
        assert "+49 123 12345" == updated_space["contactPhone"]
        assert "contact@space.com" == updated_space["contactEmail"]

        # test space avatar, cover and location deletion
        input = {
            "id": str(community.id),
            "cover": None,
            "avatar": None,
            "location": "",
        }

        response = async_to_sync(schema.execute)(
            update_space_mutation,
            context_value=benedict({"request": {"user": user}}),
            variable_values={"input": input},
        )

        assert response.errors is None

        updated_space = response.data["updateSpace"]
        assert str(community.id) == updated_space["id"]
        assert updated_space["cover"] is None
        assert updated_space["avatar"] is None
        assert updated_space["location"] is None
        assert updated_space["coverBlurhash"] is None
        assert updated_space["avatarBlurhash"] is None

    def test_space_with_tasks(self):
        user_member = make_user()
        user_external = make_user()
        space = make_community(creator=user_member)

        # create public task
        public_task = user_member.create_task(
            space_id=space.id,
            name="test_name_public",
            description="test_description",
            visibility=VisibilityType.PUBLIC,
            regularity="ONE_TIME",
            duration="INDETERMINATE",
            interaction_type="CHAT",
            location_type="REMOTE",
            contact_email="test@test.com",
            slots_available=1,
            interaction_signup_link="https://test.com",
        )

        # create members-only task
        user_member.create_task(
            space_id=space.id,
            name="test_name_private",
            description="test_description",
            visibility=VisibilityType.MEMBERS,
            regularity="ONE_TIME",
            duration="INDETERMINATE",
            interaction_type="CHAT",
            location_type="REMOTE",
            contact_email="test@test.com",
            slots_available=1,
            interaction_signup_link="https://test.com",
        )

        space_by_id_query = f"""
            query {{
                spaceById(idOrName: "{space.name}") {{
                    id
                    name
                    tasks {{
                        id
                        visibility
                    }}
                }}
            }}
            """

        # member should get all tasks
        response_member = async_to_sync(schema.execute)(
            space_by_id_query,
            context_value=benedict({"request": {"user": user_member}}),
        )
        assert response_member.errors is None
        tasks_member = response_member.data["spaceById"]["tasks"]
        assert len(tasks_member) == 2

        # non member should only get the public task
        response_external = async_to_sync(schema.execute)(
            space_by_id_query,
            context_value=benedict({"request": {"user": user_external}}),
        )

        assert response_external.errors is None
        tasks_external = response_external.data["spaceById"]["tasks"]
        assert len(tasks_external) == 1
        assert tasks_external[0].get("id") == str(public_task.id)

    @mock.patch("openbook_notifications.services.NotificationsService.send_space_membership_invite_notification")
    def test_can_invite_user_to_space(self, mock_send_space_membership_invite_notification):
        invitee = make_user()
        admin = make_user()
        space = make_community(creator=admin)

        # Preconditions
        pre_invite_space = get_space_for_user(invitee, space)
        assert pre_invite_space["connectionStatusToMyself"] == []

        # Send invite
        mutate_update_space_user_connection_data(
            auth_user=admin,
            space_id=space.id,
            user_id=invitee.id,
            connection_type=SpaceUserConnectionType.MEMBERSHIP_INVITEE,
            connect_action=UpdateConnectionAction.CONNECT,
        )

        post_invite_space = get_space_for_user(invitee, space)
        assert post_invite_space["connectionStatusToMyself"] == [SpaceUserConnectionType.MEMBERSHIP_INVITEE.value]

        # User received notification
        invitee_notifications_response = get_notifications(invitee)
        assert invitee_notifications_response["totalResults"] >= 1
        notifications = invitee_notifications_response["data"]
        space_invite_notification = next(n for n in notifications if n["notificationType"] == "CI")
        assert space_invite_notification["owner"]["fullName"] == invitee.profile.full_name()
        assert space_invite_notification["options"]["user"]["fullName"] == admin.profile.full_name()

        community_invite = space.get_membership_invite(invitee)

        # THEN invitee should receive notification via Notifications system
        mock_send_space_membership_invite_notification.assert_called_once_with(
            inviter=admin,
            recipient=invitee,
            space=space,
            community_invite=community_invite,
        )

    def test_correctly_updates_onboarding_steps(self):
        user = make_user()
        community = make_community(creator=user)

        initial_onboarding_steps = [
            {"text": "Step 1"},
            {"text": "Step 2"},
        ]
        update_and_assert_onboarding_steps(user, community.id, initial_onboarding_steps)

        onboarding_steps_add_step = [
            {"text": "Step 1"},
            {"text": "Step 1.5"},
            {"text": "Step 2"},
        ]
        update_and_assert_onboarding_steps(user, community.id, onboarding_steps_add_step)

        onboarding_steps_remove_step = [
            {"text": "Step 1.5"},
            {"text": "Step 2"},
        ]
        update_and_assert_onboarding_steps(user, community.id, onboarding_steps_remove_step)

        update_and_assert_onboarding_steps(user, community.id, [])

    def test_can_not_update_onboarding_steps_if_empty(self):
        user = make_user()
        community = make_community(creator=user)

        onboarding_steps = [
            {"text": "New step 1"},
            {"text": ""},
            {"text": "New step 3"},
        ]

        update_space_mutation = """
            mutation test($input: UpdateSpaceInput!) {
                updateSpace(input: $input) {
                    onboarding { steps { text } }
                }
            }
            """

        response = async_to_sync(schema.execute)(
            update_space_mutation,
            context_value=benedict({"request": {"user": user}}),
            variable_values={
                "input": {
                    "id": str(community.id),
                    "onboardingSteps": onboarding_steps,
                }
            },
        )

        assert response.errors is not None
        assert response.data is None
        assert "This field may not be blank." in response.errors[0].extensions["errors"]

    def test_onboarding_visible_to_all(self):
        user = make_user()
        member = make_user()
        community = make_community()
        community.add_member(member)
        onboarding_steps = [
            {"text": "Step 1"},
            {"text": "Step 2"},
        ]
        community.set_onboarding_steps(onboarding_steps)

        assert_onboarding(community.id, AnonymousUser, {"steps": onboarding_steps})
        assert_onboarding(community.id, user, {"steps": onboarding_steps})
        assert_onboarding(community.id, member, {"steps": onboarding_steps})

    def test_validates_invite_user_to_space(self):
        user = make_user()
        admin = make_user()
        member = make_user()
        invitee = make_user()
        space = make_community(creator=admin)
        space.add_member(member)
        space.create_invite(admin, invitee)
        invalid_uuid = str(uuid4())

        expected_errors = [
            {
                "field": "space_id",
                "value": None,
                "expected_error": "badly formed hexadecimal UUID string",
            },
            {
                "field": "space_id",
                "value": invalid_uuid,
                "expected_error": "No community with the provided id exists.",
            },
            {
                "field": "user_id",
                "value": invalid_uuid,
                "expected_error": "Object not found",
            },
            {
                "field": "user_id",
                "value": member.id,
                "expected_input_error": "User is already a member",
            },
            {
                "field": "user_id",
                "value": invitee.id,
                "expected_input_error": "User is already invited",
            },
            {
                "field": "auth_user",
                "value": AnonymousUser,
                "expected_error": "Unauthorized",
            },
            {
                "field": "auth_user",
                "value": user,
                "expected_input_error": "You cannot create an invite to a community you are not a member of",
            },
        ]

        for test_case in expected_errors:
            response = mutate_update_space_user_connection_raw(
                auth_user=test_case["value"] if test_case["field"] == "auth_user" else admin,
                space_id=test_case["value"] if test_case["field"] == "space_id" else space.id,
                user_id=test_case["value"] if test_case["field"] == "user_id" else user.id,
                connection_type=SpaceUserConnectionType.MEMBERSHIP_INVITEE,
                connect_action=UpdateConnectionAction.CONNECT,
            )
            if "expected_input_error" in test_case:
                field_errors = json.loads(response.errors[0].extensions["errors"])
                assert test_case["expected_input_error"] == field_errors[0]["message"]
            else:
                assert test_case["expected_error"] in str(response.errors[0].message)
            assert (response.data["updateSpaceUserConnection"] if response.data else response.data) is None

    def test_can_invite_user_to_space_by_email(self):
        community_creator = make_user()
        invite_email = "test@test.com"
        invited_user = make_user(email=invite_email)

        community = make_community(creator=community_creator)

        invite_to_space_by_email_mutation = """
            mutation InviteToSpaceByEmail($email: String!, $spaceId: UUID!) {
                inviteToSpaceByEmail(email: $email, spaceId: $spaceId) {
                    success
                }
            }
            """

        valid_input = {
            "email": invite_email,
            "spaceId": str(community.id),
        }

        response = async_to_sync(schema.execute)(
            invite_to_space_by_email_mutation,
            variable_values=valid_input,
            context_value=benedict({"request": {"user": community_creator, "META": {"HTTP_ACCEPT_LANGUAGE": "de"}}}),
        )

        assert response.data["inviteToSpaceByEmail"]["success"] is True
        assert response.errors is None

        invited_user_notifications_response = get_notifications(invited_user)
        assert invited_user_notifications_response["totalResults"] >= 1
        notifications = invited_user_notifications_response["data"]
        community_invite_notification = next(n for n in notifications if n["notificationType"] == "CI")
        assert community_invite_notification["owner"]["fullName"] == invited_user.profile.full_name()
        assert community_invite_notification["options"]["user"]["fullName"] == community_creator.profile.full_name()

    def test_can_not_invite_to_space_by_email_if_not_a_space_member(self):
        user = make_user()

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
            context_value=benedict({"request": {"user": user, "META": {"HTTP_ACCEPT_LANGUAGE": "de"}}}),
        )

        field_errors = json.loads(response.errors[0].extensions["errors"])

        assert field_errors[0]["message"] in "You cannot create an invite to a community you are not a member of"

    def test_can_not_invite_to_space_by_email_missing_required_fields(self):
        user = make_user()
        community = make_community(creator=user)

        invite_to_space_by_email_mutation = """
            mutation InviteToSpaceByEmail($email: String!, $spaceId: UUID!) {
                inviteToSpaceByEmail(email: $email, spaceId: $spaceId) {
                    success
                }
            }
            """

        response_no_email = async_to_sync(schema.execute)(
            invite_to_space_by_email_mutation,
            context_value=benedict({"request": {"user": user, "META": {"HTTP_ACCEPT_LANGUAGE": "de"}}}),
            variable_values={"spaceId": str(community.id)},
        )

        response_no_space_id = async_to_sync(schema.execute)(
            invite_to_space_by_email_mutation,
            context_value=benedict({"request": {"user": user, "META": {"HTTP_ACCEPT_LANGUAGE": "de"}}}),
            variable_values={"email": "test@test.com"},
        )

        assert "Variable '$email' of required type 'String!' was not provided." in str(
            response_no_email.errors[0].message
        )
        assert "Variable '$spaceId' of required type 'UUID!' was not provided." in str(
            response_no_space_id.errors[0].message
        )

    @mock.patch("openbook_auth.tasks.requests.delete")
    @mock.patch("openbook_auth.schema.mutations.publish_user_deleted_event")
    @mock.patch("openbook_auth.schema.mutations.publish_space_deleted_event")
    def test_cannot_delete_space_if_deleted_authenticated_user_not_only_admin(
        self, mock_publish_space_deleted_event, mock_publish_user_deleted_event, mock_delete
    ):
        response = Response()
        response.status_code = 204
        response._content = str.encode(json.dumps({}))
        mock_delete.return_value = response

        user = make_user(name="Fritz", last_name="Meier")
        space = make_community(creator=user)

        admin = make_user(name="John", last_name="Doe")
        space.add_member(admin)
        space.add_administrator(admin)

        mutation_response = async_to_sync(schema.execute)(
            """
            mutation test {
                deleteAuthenticatedUser {
                    success
                }
            }
            """,
            context_value=benedict({"request": {"user": user}}),
        )
        mock_delete.assert_called_once_with(
            f"{settings.ORY_BASE_URL}/admin/identities/{user.username}",
            headers={"Authorization": f"Bearer {settings.ORY_ACCESS_TOKEN}"},
        )

        assert mutation_response.data["deleteAuthenticatedUser"]["success"] is True

        mock_publish_user_deleted_event.assert_called_once_with(user=user)
        mock_publish_space_deleted_event.assert_not_called()

    def test_favorited_task_responds_is_favorite_for_authenticated_user(self):
        user = make_user()
        space = make_community()
        task = make_community_task(space, visibility=VisibilityType.PUBLIC)
        UserFavorite.favorite(user, FavoritableType.TASK, task.id)

        query = f"""
            query {{
                taskById(id: "{task.id}") {{
                    isFavorite
                }}
            }}
        """

        response = async_to_sync(schema.execute)(query, context_value=benedict({"request": {"user": user}}))

        assert response.errors is None
        assert response.data["taskById"]["isFavorite"] is True
