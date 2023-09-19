import logging

import pytest
from asgiref.sync import async_to_sync
from benedict import benedict
from django.core.management import call_command
from django.test import AsyncClient

from openbook.graphql_schema import schema
from openbook_common.enums import VisibilityType
from openbook_common.tests.helpers import (
    make_community,
    make_fake_post_text,
    make_fake_post_title,
    make_user,
)
from openbook_communities.models import CommunityNotificationsSubscription
from openbook_connections.tests.helpers import connect_to_user, disconnect_from_user
from openbook_notifications.tests.helpers import (
    get_notifications,
    has_new_notifications,
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
class TestNotifications:
    def test_notifications(self):
        followed_user = make_user(name="Peter", last_name="Pep")
        following_user = make_user(name="Other")

        connect_to_user(following_user, followed_user)

        response = get_notifications(followed_user)
        assert response["totalResults"] >= 1
        notifications = response["data"]
        connection_requested_notification = next(n for n in notifications if n["notificationType"] == "CR")
        assert connection_requested_notification["owner"]["fullName"] == followed_user.profile.full_name()
        assert connection_requested_notification["options"]["user"]["fullName"] == following_user.profile.full_name()

        connect_to_user(followed_user, following_user)

        notifications = get_notifications(followed_user)["data"]
        connection_accepted_notification = next(n for n in notifications if n["notificationType"] == "CA")
        assert connection_accepted_notification["options"]["user"]["fullName"] == following_user.profile.full_name()

        notifications = get_notifications(following_user)["data"]
        connection_confirmed_notification = next(n for n in notifications if n["notificationType"] == "CC")
        assert connection_confirmed_notification["options"]["user"]["fullName"] == followed_user.profile.full_name()

    def test_community_new_post_notifications(self):
        post_user = make_user()
        subscriber_user = make_user()

        space = make_community(creator=post_user)
        space.add_member(subscriber_user)
        CommunityNotificationsSubscription.enable_new_post_notification_for_community(
            community=space, subscriber=subscriber_user
        )

        post1 = post_user.create_community_post(
            text=make_fake_post_text(),
            title=make_fake_post_title(),
            space_id=space.id,
            visibility=VisibilityType.MEMBERS.value,
        )

        response = get_notifications(subscriber_user)
        assert response["totalResults"] == 1

        notification = response["data"][0]
        assert notification["options"]["post"]["title"] == post1.title
        assert notification["options"]["teaser"] == post1.title

        post2 = post_user.create_community_post(
            text=make_fake_post_text(),
            space_id=space.id,
            visibility=VisibilityType.MEMBERS.value,
        )

        response = get_notifications(subscriber_user)
        assert response["totalResults"] == 2

        notification = response["data"][0]
        assert notification["options"]["post"]["title"] is None
        expected_teaser = " ".join(post2.text.split()[:3]) + "..."
        assert notification["options"]["teaser"] == expected_teaser

    def test_community_admin_privileges_notifications(self):
        space_user = make_user()
        creator_user = make_user()

        space = make_community(creator=creator_user)
        space.add_member(space_user)

        CommunityNotificationsSubscription.enable_new_post_notification_for_community(
            community=space, subscriber=space_user
        )

        creator_user.add_administrator_with_username_to_community_with_name(space_user.username, space.name)

        response = get_notifications(space_user)
        assert response["totalResults"] == 1

        notification = response["data"][0]

        assert notification["notificationType"] == "CAPG"
        assert notification["options"]["space"]["title"] == space.name
        assert notification["options"]["user"]["fullName"] == space_user.profile.full_name()

        creator_user.remove_administrator_with_username_from_community_with_name(space_user.username, space.name)

        response = get_notifications(space_user)
        assert response["totalResults"] == 2

        notification = response["data"][0]
        assert notification["notificationType"] == "CAPR"
        assert notification["options"]["space"]["title"] == space.name
        assert notification["options"]["user"]["fullName"] == space_user.profile.full_name()

    def test_has_new_notifications(self):
        followed_user = make_user(name="Peter", last_name="Pep")
        following_user = make_user(name="Other")
        following_user2 = make_user(name="Other2")

        assert has_new_notifications(followed_user)["status"] is False

        connect_to_user(following_user, followed_user)
        assert has_new_notifications(followed_user)["status"] is True

        disconnect_from_user(following_user, followed_user)
        assert has_new_notifications(followed_user)["status"] is False

        connect_to_user(following_user, followed_user)
        assert has_new_notifications(followed_user)["status"] is True

        data = get_notifications(followed_user)
        first_notification_id = data["data"][0]["id"]
        response = async_to_sync(schema.execute)(
            """
            mutation LastSeenNotification($id: UUID!){
                lastSeenNotification(notificationId: $id) {
                    status
                }
            }
            """,
            variable_values={"id": str(first_notification_id)},
            context_value=benedict({"request": {"user": followed_user}}),
        )
        assert response.data["lastSeenNotification"]["status"] is False
        assert has_new_notifications(followed_user)["status"] is False

        connect_to_user(following_user2, followed_user)
        assert has_new_notifications(followed_user)["status"] is True
