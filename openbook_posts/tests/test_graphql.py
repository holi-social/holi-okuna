import logging
from unittest import mock, TestCase

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.management import call_command
from django.test import AsyncClient

from openbook_auth.models import User
from openbook_common.enums import VisibilityType
from openbook_common.tests.helpers import (
    make_community,
    make_fake_post_text,
    make_fake_post_title,
    make_user,
    simple_jpeg_bytes,
)
from openbook_common.utils.model_loaders import get_community_model
from openbook_communities.models import CommunityNotificationsSubscription
from openbook_notifications.models import CommunityNewPostNotification
from openbook_posts.models import (
    Post,
    PostComment,
    PostCommentReaction,
    PostImage,
    PostUserMention,
)
from openbook_posts.tests.helpers import (
    create_space_post,
    create_space_post_2,
    delete_post_comment,
    delete_space_post,
    get_post_with_id_data,
    get_post_with_id_raw,
    react_to_post,
    react_to_post_comment,
    update_space_post,
    update_post_comment,
)

from openbook_common.enums import FeatureToggleName, FeatureToggleType
from openbook_common.models import FeatureToggle as FeatureToggleModel

logger = logging.getLogger(__name__)


@pytest.fixture(scope="session")
def client():
    return AsyncClient()


@pytest.fixture(scope="session")
def django_db_setup(django_db_setup, django_db_blocker):
    with django_db_blocker.unblock():
        call_command("loaddata", "openbook_moderation/fixtures/moderation_categories.json")


@pytest.mark.django_db
class TestPosts(TestCase):
    def setup(self):
        self.notifications_toggle = FeatureToggleModel.objects.create(
            name=FeatureToggleName.NOTIFICATIONS.value, status=FeatureToggleType.PRODUCTION
        )

    def teardown(self):
        if self.notifications_toggle.id is not None:
            self.notifications_toggle.delete()

    @mock.patch("openbook_notifications.notifications.Notifications.send_post_comment_mention_notification")
    @mock.patch("openbook_notifications.notifications.Notifications.send_post_comment_author_notification")
    def test_can_mention_user_in_post_comment(
        self, mock_send_post_comment_author_notification, mock_send_post_comment_mention_notification
    ):
        posting_user = make_user()
        mentioned_user = make_user(name="Mentioned")
        commenter = make_user(name="Commenter")

        post_text = make_fake_post_text()
        post_title = make_fake_post_title()

        post = posting_user.create_post(text=post_text, title=post_title, is_public=True)

        input_data = {
            "postId": str(post.id),
            "text": f"comment text 1 @{mentioned_user.username}",
        }

        response = update_post_comment(commenter, input_data)
        assert response.errors is None

        post_comment_data = response.data["updatePostComment"]["postComment"]
        post_comment = PostComment.objects.get(id=post_comment_data["id"])

        mock_send_post_comment_mention_notification.assert_called_once_with(post_comment=post_comment)
        mock_send_post_comment_author_notification.assert_called_once_with(post_comment=post_comment)

    @mock.patch("openbook_notifications.notifications.Notifications.send_post_comment_mention_notification")
    @mock.patch("openbook_notifications.notifications.Notifications.send_post_comment_author_notification")
    def test_skip_post_comment_author_notification_if_author_is_commenter(
        self, mock_send_post_comment_author_notification, mock_send_post_comment_mention_notification
    ):
        posting_user = make_user()
        mentioned_user = make_user(name="Mentioned")

        post_text = make_fake_post_text()
        post_title = make_fake_post_title()

        post = posting_user.create_post(text=post_text, title=post_title, is_public=True)

        input_data = {
            "postId": str(post.id),
            "text": f"comment text 1 @{mentioned_user.username}",
        }

        response = update_post_comment(posting_user, input_data)
        assert response.errors is None

        post_comment_data = response.data["updatePostComment"]["postComment"]
        post_comment = PostComment.objects.get(id=post_comment_data["id"])

        mock_send_post_comment_mention_notification.assert_called_once_with(post_comment=post_comment)
        mock_send_post_comment_author_notification.assert_not_called()

    @mock.patch("openbook_notifications.notifications.Notifications.send_post_comment_mention_notification")
    @mock.patch("openbook_notifications.notifications.Notifications.send_post_comment_author_notification")
    def test_skip_post_comment_author_notification_if_author_is_mentioned(
        self, mock_send_post_comment_author_notification, mock_send_post_comment_mention_notification
    ):
        posting_user = make_user()
        commenter = make_user(name="Commenter")

        post_text = make_fake_post_text()
        post_title = make_fake_post_title()

        post = posting_user.create_post(text=post_text, title=post_title, is_public=True)

        input_data = {
            "postId": str(post.id),
            "text": f"comment text 1 @{posting_user.username}",
        }

        response = update_post_comment(commenter, input_data)
        assert response.errors is None

        post_comment_data = response.data["updatePostComment"]["postComment"]
        post_comment = PostComment.objects.get(id=post_comment_data["id"])

        mock_send_post_comment_mention_notification.assert_called_once_with(post_comment=post_comment)
        mock_send_post_comment_author_notification.assert_not_called()

    def test_can_fetch_post(self):
        posting_user = make_user()
        mentioned_user = make_user(name="Mentioned")
        other_user = make_user(name="Other")

        post_text = make_fake_post_text()
        post_title = make_fake_post_title()

        post = posting_user.create_post(text=post_text, title=post_title, is_public=True)
        post.comment(text=f"comment text 1 @{posting_user.username}", commenter=other_user)
        post.comment(
            text=f"comment text 2 @{mentioned_user.username} @{posting_user.username}",
            commenter=other_user,
        )
        post.comment(
            text=f"comment text 3 @{mentioned_user.username} @{posting_user.username}",
            commenter=other_user,
        )

        post_data = get_post_with_id_data(post)

        assert post_data["text"] == post_text
        assert post_data["title"] == post_title
        assert post_data["image"] is None
        assert post_data["creator"]["id"] == str(posting_user.uuid)
        assert post_data["created"] is not None
        assert post_data["numberOfComments"] == 3
        assert post_data["involvedUsers"]["totalResults"] == 2
        assert len(post_data["comments"]) == 3
        assert post_data["comments"][0]["text"] == f"comment text 1 @{posting_user.username}"
        assert post_data["commenters"]["totalResults"] == 1
        assert post_data["commenters"]["data"][0]["firstName"] == other_user.name

    def test_can_fetch_post_with_image(self):
        posting_user = make_user()

        post_text = make_fake_post_text()
        post_title = make_fake_post_title()
        image_name = "foo.jpg"

        post = posting_user.create_post(
            text=post_text,
            title=post_title,
            image=SimpleUploadedFile(name=image_name, content=simple_jpeg_bytes),
            is_public=True,
        )

        post_data = get_post_with_id_data(post)

        assert post_data["text"] == post_text
        assert post_data["title"] == post_title
        assert image_name in post_data["image"]["url"]
        assert post_data["image"]["width"] == 1
        assert post_data["image"]["height"] == 1
        assert post_data["creator"]["id"] == str(posting_user.uuid)
        assert post_data["created"] is not None

    def test_cant_fetch_deleted_post(self):
        posting_user = make_user()

        post = posting_user.create_post(
            text=make_fake_post_text(),
            is_public=True,
        )
        post_id = post.id
        post.delete()

        response = get_post_with_id_raw(post_id)

        post_data = response.data["postById"]
        assert post_data is None
        assert "Object not found" in response.errors[0].message

    def test_cant_fetch_post_draft(self):
        posting_user = make_user()

        post_text = make_fake_post_text()
        post_title = make_fake_post_title()

        post = posting_user.create_post(text=post_text, title=post_title, is_draft=True, is_public=True)

        response = get_post_with_id_raw(post.id)

        post_data = response.data["postById"]
        assert post_data is None
        assert "Forbidden" in response.errors[0].message

    def test_can_fetch_own_post_draft(self):
        posting_user = make_user()

        post_text = make_fake_post_text()
        post_title = make_fake_post_title()

        post = posting_user.create_post(text=post_text, title=post_title, is_draft=True, is_public=True)

        response = get_post_with_id_raw(post.id, posting_user)

        post_data = response.data["postById"]
        assert post_data["text"] == post_text
        assert response.errors is None

    def test_can_fetch_public_space_post(self):
        posting_user = make_user()
        space = make_community(creator=posting_user)

        post_text = make_fake_post_text()
        post_title = make_fake_post_title()

        post = posting_user.create_community_post(
            space_id=space.id, text=post_text, title=post_title, visibility=VisibilityType.PUBLIC.value
        )

        response = get_post_with_id_raw(post.id)

        post_data = response.data["postById"]
        assert post_data["text"] == post_text
        assert response.errors is None

    def test_can_fetch_space_collaborators_post_as_member(self):
        member = make_user()
        posting_user = make_user()
        space = make_community(creator=posting_user)
        space.add_member(member)

        post_text = make_fake_post_text()
        post_title = make_fake_post_title()

        post = posting_user.create_community_post(
            space_id=space.id, text=post_text, title=post_title, visibility=VisibilityType.MEMBERS.value
        )

        response = get_post_with_id_raw(post.id, member)

        post_data = response.data["postById"]
        assert post_data["text"] == post_text
        assert response.errors is None

    def test_cant_fetch_space_collaborators_post_if_not_member(self):
        user = make_user()
        posting_user = make_user()
        space = make_community(creator=posting_user)

        post_text = make_fake_post_text()
        post_title = make_fake_post_title()

        post = posting_user.create_community_post(
            space_id=space.id, text=post_text, title=post_title, visibility=VisibilityType.MEMBERS.value
        )

        response = get_post_with_id_raw(post.id, user)

        post_data = response.data["postById"]
        assert post_data is None
        assert "Forbidden" in response.errors[0].message

    def test_can_delete_post_comment(self):
        posting_user = make_user()
        comment_user = make_user()

        post_text = make_fake_post_text()
        post_title = make_fake_post_title()

        post = posting_user.create_post(text=post_text, title=post_title, is_public=True)
        comment = post.comment(text=f"comment text", commenter=comment_user)
        reaction = comment.react(posting_user, "HEART")
        post.comment(text=f"comment text 2", commenter=comment_user)

        assert post.comments.count() == 2
        response = delete_post_comment(comment.id, comment_user)
        assert response.errors is None
        assert response.data["deletePostComment"]["success"] == True
        assert post.comments.count() == 1
        assert comment.id not in post.comments.values_list("id", flat=True)
        assert reaction.id not in PostCommentReaction.objects.filter(post_comment=comment).values_list("id", flat=True)

    def test_cant_delete_post_comment_of_other_user(self):
        posting_user = make_user()
        comment_user = make_user()
        other_user = make_user()

        post_text = make_fake_post_text()
        post_title = make_fake_post_title()

        post = posting_user.create_post(text=post_text, title=post_title, is_public=True)
        comment = post.comment(text=f"comment text", commenter=comment_user)
        reaction = comment.react(posting_user, "HEART")
        post.comment(text=f"comment text 2", commenter=comment_user)

        assert post.comments.count() == 2
        response = delete_post_comment(comment.id, other_user)
        assert response.data is None

        assert post.comments.count() == 2
        assert comment.id in post.comments.values_list("id", flat=True)
        assert reaction.id in PostCommentReaction.objects.filter(post_comment=comment).values_list("id", flat=True)

    def test_cant_delete_post_comment_not_exist(self):
        posting_user = make_user()
        comment_user = make_user()
        other_user = make_user()

        post_text = make_fake_post_text()
        post_title = make_fake_post_title()

        post = posting_user.create_post(text=post_text, title=post_title, is_public=True)
        comment = post.comment(text=f"comment text", commenter=comment_user)
        reaction = comment.react(posting_user, "HEART")
        post.comment(text=f"comment text 2", commenter=comment_user)

        assert post.comments.count() == 2
        response = delete_post_comment("00000000-0000-0000-0000-000000000000", comment_user)
        assert response.data is None

        assert post.comments.count() == 2
        assert comment.id in post.comments.values_list("id", flat=True)
        assert reaction.id in PostCommentReaction.objects.filter(post_comment=comment).values_list("id", flat=True)

    def test_react_to_post(self):
        posting_user = make_user()
        other_user = make_user(name="Other")

        post_text = make_fake_post_text()
        post_title = make_fake_post_title()

        post = posting_user.create_post(text=post_text, title=post_title, is_public=True)

        react_to_post(post, "SET", posting_user)
        executed = react_to_post(post, "SET", posting_user)  # setting twice is same as setting once
        updated_post = executed.data["updatePostReaction"]

        assert updated_post["myReaction"]["HEART"] == 1
        assert updated_post["reactions"]["HEART"] == 1

        post_data = get_post_with_id_data(post, other_user)
        assert post_data["myReaction"]["HEART"] == 0
        assert post_data["reactions"]["HEART"] == 1

        react_to_post(post, "REMOVE", posting_user)
        executed = react_to_post(post, "REMOVE", posting_user)  # setting twice is same as setting once
        updated_post = executed.data["updatePostReaction"]
        assert updated_post["myReaction"]["HEART"] == 0
        assert updated_post["reactions"]["HEART"] == 0

    def test_react_to_post_comment(self):
        posting_user = make_user()
        other_user = make_user(name="Other")

        post_text = make_fake_post_text()
        post_title = make_fake_post_title()

        post = posting_user.create_post(text=post_text, title=post_title, is_public=True)
        comment = post.comment(text=f"comment text", commenter=other_user)

        react_to_post_comment(comment, "SET", posting_user)
        executed = react_to_post_comment(comment, "SET", posting_user)  # setting twice is same as setting once
        updated_post_comment = executed.data["updatePostCommentReaction"]

        assert updated_post_comment["myReaction"]["HEART"] == 1
        assert updated_post_comment["reactions"]["HEART"] == 1

        post_data = get_post_with_id_data(post, other_user)
        assert post_data["myReaction"]["HEART"] == 0
        assert post_data["reactions"]["HEART"] == 0
        assert post_data["comments"][0]["myReaction"]["HEART"] == 0
        assert post_data["comments"][0]["reactions"]["HEART"] == 1

        react_to_post_comment(comment, "REMOVE", posting_user)
        executed = react_to_post_comment(comment, "REMOVE", posting_user)  # setting twice is same as setting once
        updated_post_comment = executed.data["updatePostCommentReaction"]
        assert updated_post_comment["myReaction"]["HEART"] == 0
        assert updated_post_comment["reactions"]["HEART"] == 0

    def test_space_user_can_create_space_post(self):
        space_admin = make_user()
        member_user = make_user()
        space = make_community(creator=space_admin)
        space.add_member(member_user)

        # space admin can create public post
        input_data = {
            "spaceId": str(space.id),
            "visibility": VisibilityType.PUBLIC.value,
            "text": make_fake_post_text(),
        }

        response = create_space_post(space_admin, input_data)

        data = response.data["createSpacePost"]
        posts_data = data["posts"]["data"]

        assert data["id"] == str(space.id)
        assert data["posts"]["totalResults"] == 1
        assert posts_data[0]["text"] == input_data["text"]
        assert posts_data[0]["isPublic"] is True

        # space admin can create private post
        input_data = {
            "spaceId": str(space.id),
            "visibility": VisibilityType.MEMBERS.value,
            "text": make_fake_post_text(),
        }

        response = create_space_post(space_admin, input_data)

        data = response.data["createSpacePost"]
        posts_data = data["posts"]["data"]

        assert data["id"] == str(space.id)
        assert data["posts"]["totalResults"] == 2
        assert posts_data[0]["text"] == input_data["text"]
        assert posts_data[0]["isPublic"] is False

    def test_member_user_can_create_only_member_visibility_space_post(self):
        space_admin = make_user()
        member_user = make_user()
        space = make_community(creator=space_admin)
        space.add_member(member_user)

        # member user can create private post
        input_data = {
            "spaceId": str(space.id),
            "visibility": VisibilityType.MEMBERS.value,
            "text": make_fake_post_text(),
        }

        response = create_space_post(member_user, input_data)

        data = response.data["createSpacePost"]
        posts_data = data["posts"]["data"]

        assert data["id"] == str(space.id)
        assert data["posts"]["totalResults"] == 1
        assert posts_data[0]["text"] == input_data["text"]
        assert posts_data[0]["isPublic"] is False

        # member user cannot create public post
        input_data = {
            "spaceId": str(space.id),
            "visibility": VisibilityType.PUBLIC.value,
            "text": make_fake_post_text(),
        }

        response = create_space_post(member_user, input_data)

        assert response.errors is not None
        assert response.data is None
        assert (
            "You cannot add a public post to a community you're not administrator of"
            in response.errors[0].extensions["errors"]
        )

    def test_cant_create_space_post_external_user(self):
        space_admin = make_user()
        external_user = make_user()
        space = make_community(creator=space_admin)

        # not member user can't create post for the space
        input_data = {
            "spaceId": str(space.id),
            "visibility": VisibilityType.MEMBERS.value,
            "text": make_fake_post_text(),
        }

        response = create_space_post(external_user, input_data)

        assert response.errors is not None
        assert response.data is None
        assert "You cannot post to a community you're not member of" in response.errors[0].extensions["errors"]

    def test_cant_create_space_post_invalid_input(self):
        space_admin = make_user()
        space = make_community(creator=space_admin)

        # test space id field is missing
        input_data = {
            "visibility": VisibilityType.MEMBERS.value,
            "text": make_fake_post_text(),
        }

        response = create_space_post(space_admin, input_data)
        assert response.errors is not None
        assert response.data is None
        assert "Field 'spaceId' of required type 'UUID!' was not provided" in response.errors[0].message

        # test post text field is missing
        input_data = {
            "spaceId": str(space.id),
            "visibility": VisibilityType.PUBLIC.value,
        }

        response = create_space_post(space_admin, input_data)
        assert response.errors is not None
        assert response.data is None
        assert "Field 'text' of required type 'String!' was not provided" in response.errors[0].message

        # test visibility field is missing
        input_data = {"spaceId": str(space.id), "text": make_fake_post_text()}

        response = create_space_post(space_admin, input_data)
        assert response.errors is not None
        assert response.data is None
        assert "Field 'visibility' of required type 'VisibilityType!' was not provided" in response.errors[0].message

    @mock.patch("openbook_notifications.notifications.Notifications.send_space_new_post_notification")
    def test_space_user_can_create_space_post_2(self, mock_send_space_new_post_notification):
        space_admin = make_user()
        member_user = make_user()
        space = make_community(creator=space_admin)
        space.add_member(member_user)
        space.add_moderator(member_user)

        # space admin can create public post
        input_data = {
            "spaceId": str(space.id),
            "visibility": VisibilityType.PUBLIC.value,
            "text": make_fake_post_text(),
        }

        response = create_space_post_2(space_admin, input_data)

        data = response.data["createSpacePost2"]

        assert data["text"] == input_data["text"]
        assert data["isPublic"] is True

        post_id = data["id"]
        post = Post.objects.get(id=post_id)

        mock_send_space_new_post_notification.assert_called_with(post=post, collaborators=[member_user])

        # space admin can create private post
        input_data = {
            "spaceId": str(space.id),
            "visibility": VisibilityType.MEMBERS.value,
            "text": make_fake_post_text(),
        }

        response = create_space_post_2(space_admin, input_data)

        data = response.data["createSpacePost2"]

        assert data["text"] == input_data["text"]
        assert data["isPublic"] is False

        post_id = data["id"]
        post = Post.objects.get(id=post_id)

        mock_send_space_new_post_notification.assert_called_with(post=post, collaborators=[member_user])

    @mock.patch("openbook_notifications.notifications.Notifications.send_space_new_post_notification")
    def test_member_user_can_create_only_member_visibility_space_post_2(self, mock_send_space_new_post_notification):
        space_admin = make_user()
        member_user = make_user()
        space = make_community(creator=space_admin)
        space.add_member(member_user)
        space.add_moderator(member_user)

        # member user can create private post
        input_data = {
            "spaceId": str(space.id),
            "visibility": VisibilityType.MEMBERS.value,
            "text": make_fake_post_text(),
        }

        response = create_space_post_2(member_user, input_data)

        data = response.data["createSpacePost2"]

        assert data["text"] == input_data["text"]
        assert data["isPublic"] == False

        post_id = data["id"]
        post = Post.objects.get(id=post_id)

        mock_send_space_new_post_notification.assert_called_once_with(post=post, collaborators=[space_admin])

        # member user cannot create public post
        input_data = {
            "spaceId": str(space.id),
            "visibility": VisibilityType.PUBLIC.value,
            "text": make_fake_post_text(),
        }

        response = create_space_post_2(member_user, input_data)

        assert response.errors is not None
        assert response.data is None
        assert (
            "You cannot add a public post to a community you're not administrator of"
            in response.errors[0].extensions["errors"]
        )

    def test_cant_create_space_post_external_user_2(self):
        space_admin = make_user()
        external_user = make_user()
        space = make_community(creator=space_admin)

        # not member user can't create post for the space
        input_data = {
            "spaceId": str(space.id),
            "visibility": VisibilityType.MEMBERS.value,
            "text": make_fake_post_text(),
        }

        response = create_space_post_2(external_user, input_data)

        assert response.errors is not None
        assert response.data is None
        assert "You cannot post to a community you're not member of" in response.errors[0].extensions["errors"]

    def test_cant_create_space_post_invalid_input_2(self):
        space_admin = make_user()
        space = make_community(creator=space_admin)

        # test space id field is missing
        input_data = {
            "visibility": VisibilityType.MEMBERS.value,
            "text": make_fake_post_text(),
        }

        response = create_space_post_2(space_admin, input_data)
        assert response.errors is not None
        assert response.data is None
        assert "Field 'spaceId' of required type 'UUID!' was not provided" in response.errors[0].message

        # test post text field is missing
        input_data = {
            "spaceId": str(space.id),
            "visibility": VisibilityType.PUBLIC.value,
        }

        response = create_space_post_2(space_admin, input_data)
        assert response.errors is not None
        assert response.data is None
        assert "Field 'text' of required type 'String!' was not provided" in response.errors[0].message

        # test visibility field is missing
        input_data = {"spaceId": str(space.id), "text": make_fake_post_text()}

        response = create_space_post_2(space_admin, input_data)
        assert response.errors is not None
        assert response.data is None
        assert "Field 'visibility' of required type 'VisibilityType!' was not provided" in response.errors[0].message

    def test_space_user_can_edit_space_post(self):
        space_admin = make_user()
        posting_user = make_user()
        space = make_community(creator=space_admin)
        space.add_member(posting_user)
        space.add_administrator(posting_user)

        space_post = Post.create_post(
            creator=posting_user,
            community_id=space.id,
            image=SimpleUploadedFile(name="foo.jpg", content=simple_jpeg_bytes),
            text=make_fake_post_text(),
            title=make_fake_post_title(),
            is_public=False,
        )

        valid_image = SimpleUploadedFile(name="cover.jpg", content=simple_jpeg_bytes)

        # test post update with replace of the post image
        input_data = {
            "postId": str(space_post.id),
            "visibility": VisibilityType.PUBLIC.value,
            "text": make_fake_post_text(),
            "title": None,
            "image": valid_image,
        }

        response = update_space_post(posting_user, input_data)
        assert response.errors is None
        assert response.data is not None

        data = response.data["updateSpacePost"]
        assert data["id"] == str(space_post.id)
        assert data["space"]["posts"]["totalResults"] == 1

        assert data["title"] is None
        assert data["text"] == input_data["text"]
        assert data["isPublic"] is True
        assert "/cover.jpg/" in data["image"]["url"]
        assert data["image"]["blurhash"] is not None

        # test post update with removal of the post image
        input_data = {
            "postId": str(space_post.id),
            "visibility": VisibilityType.PUBLIC.value,
            "text": make_fake_post_text(),
            "title": None,
            "image": None,
        }

        response = update_space_post(posting_user, input_data)
        assert response.errors is None
        assert response.data is not None

        data = response.data["updateSpacePost"]
        assert data["id"] == str(space_post.id)
        assert data["space"]["posts"]["totalResults"] == 1
        assert data["title"] is None
        assert data["text"] == input_data["text"]
        assert data["isPublic"] is True
        assert data["image"] is None

    def test_cant_edit_space_post_to_public_visibility_member_user(self):
        space_admin = make_user()
        posting_user = make_user()
        space = make_community(creator=space_admin)
        space.add_member(posting_user)

        post_title = make_fake_post_title()
        post_text = make_fake_post_text()
        space_post = Post.create_post(
            creator=posting_user,
            community_id=space.id,
            image=SimpleUploadedFile(name="foo.jpg", content=simple_jpeg_bytes),
            text=post_text,
            title=post_title,
            is_public=False,
        )

        input_data = {
            "postId": str(space_post.id),
            "visibility": VisibilityType.PUBLIC.value,
            "text": make_fake_post_text(),
            "title": make_fake_post_title(),
        }

        response = update_space_post(posting_user, input_data)
        assert response.errors is not None
        assert response.data is None
        assert (
            "You cannot add a public post to a community you're not administrator of"
            in response.errors[0].extensions["errors"]
        )

        space_post.refresh_from_db()
        assert space_post.title == post_title
        assert "/foo.jpg/" in space_post.image.image.url

    def test_cant_edit_space_post_other_user(self):
        space_admin = make_user()
        posting_user = make_user()
        other_user = make_user()
        space = make_community(creator=space_admin)
        space.add_member(posting_user)
        space.add_member(other_user)

        post_title = make_fake_post_title()
        post_text = make_fake_post_text()
        space_post = Post.create_post(
            creator=posting_user,
            community_id=space.id,
            image=SimpleUploadedFile(name="foo.jpg", content=simple_jpeg_bytes),
            text=post_text,
            title=post_title,
            is_public=False,
        )

        valid_image = SimpleUploadedFile(name="cover.jpg", content=simple_jpeg_bytes)

        input_data = {
            "postId": str(space_post.id),
            "visibility": VisibilityType.MEMBERS.value,
            "text": make_fake_post_text(),
            "title": None,
            "image": valid_image,
        }

        response = update_space_post(other_user, input_data)
        assert response.errors is not None
        assert response.data is None
        assert response.errors[0].message == "This post does not belong to you."

        space_post.refresh_from_db()
        assert space_post.title == post_title
        assert "/foo.jpg/" in space_post.image.image.url

    def test_can_delete_space_post(self):
        space_admin = make_user()
        posting_user = make_user()
        subscriber_user = make_user()
        image_name = "test-image.jpg"

        space = make_community(creator=space_admin)
        space.add_member(posting_user)
        space.add_member(subscriber_user)

        CommunityNotificationsSubscription.enable_new_post_notification_for_community(
            community=space, subscriber=subscriber_user
        )

        post = posting_user.create_community_post(
            space.id,
            text=make_fake_post_text(),
            title=make_fake_post_title(),
            image=SimpleUploadedFile(name=image_name, content=simple_jpeg_bytes),
            visibility=VisibilityType.MEMBERS.value,
        )
        PostUserMention.create_post_user_mention(user=space_admin, post=post)
        PostComment.create_comment(text=make_fake_post_text(), post=post, commenter=posting_user)

        response = delete_space_post(post.id, posting_user)

        assert response.errors is None
        assert response.data["deleteSpacePost"]["posts"]["totalResults"] == 0

        assert CommunityNewPostNotification.objects.filter(post=post).count() == 0
        assert PostUserMention.objects.filter(post=post).count() == 0
        assert PostComment.objects.filter(post=post).count() == 0
        assert PostImage.objects.filter(post=post).count() == 0

    def test_can_not_delete_space_post(self):
        space_admin = make_user()
        posting_user = make_user()
        image_name = "test-image.jpg"

        space = make_community(creator=space_admin)
        space.add_member(posting_user)

        post = posting_user.create_community_post(
            space.id,
            text=make_fake_post_text(),
            title=make_fake_post_title(),
            image=SimpleUploadedFile(name=image_name, content=simple_jpeg_bytes),
            visibility=VisibilityType.MEMBERS.value,
        )
        PostUserMention.create_post_user_mention(user=space_admin, post=post)
        PostComment.create_comment(text=make_fake_post_text(), post=post, commenter=posting_user)

        response = delete_space_post(post.id, space_admin)

        assert response.data is None
        assert response.errors is not None
        assert "Bad user input" == str(response.errors[0].message)

        query_post = Post.objects.get(id=post.id)
        assert query_post.id == post.id
        assert query_post.title == post.title

        assert PostUserMention.objects.filter(post=post).count() == 1
        assert PostComment.objects.filter(post=post).count() == 1
        assert PostImage.objects.filter(post=post).count() == 1
