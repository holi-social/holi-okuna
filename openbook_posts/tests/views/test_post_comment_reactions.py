# Create your tests here.
import json
from unittest import mock
from unittest.mock import patch

from django.urls import reverse
from faker import Faker
from rest_framework import status
from openbook_common.tests.models import OpenbookAPITestCase

import logging

from openbook_common.tests.helpers import (
    make_authentication_headers_for_user,
    make_fake_post_text,
    make_fake_post_comment_text,
    make_user,
    make_circle,
    make_community,
)
from openbook_common.types import ReactionType
from openbook_common.utils.test import uuid_id_parser
from openbook_notifications.models import PostCommentReactionNotification
from openbook_posts.models import PostCommentReaction

logger = logging.getLogger(__name__)
fake = Faker()


def send_post_comment_reaction_push_notification_mock(post_comment_reaction):
    return post_comment_reaction


class PostCommentReactionsAPITests(OpenbookAPITestCase):
    """
    PostCommentReactionsAPI
    """

    fixtures = ["openbook_circles/fixtures/circles.json"]

    def test_can_react_to_own_post_comment(self):
        """should be able to react in own post comment and return 201"""
        user = make_user()
        headers = make_authentication_headers_for_user(user)
        post = user.create_public_post(text=make_fake_post_text())
        post_comment = user.comment_post(post=post, text=make_fake_post_comment_text())

        data = self._get_create_post_comment_reaction_request_data(ReactionType.HEART)

        url = self._get_url(post=post, post_comment=post_comment)
        response = self.client.put(url, data, **headers)

        self.assertEqual(status.HTTP_201_CREATED, response.status_code)
        self.assertTrue(
            PostCommentReaction.objects.filter(
                post_comment_id=post_comment.pk,
                reaction_type=ReactionType.HEART,
                reactor_id=user.pk,
            ).count()
            == 1
        )

    def test_can_react_to_post_comment_reply(self):
        """should be able to react to post comment reply and return 201"""
        user = make_user()
        headers = make_authentication_headers_for_user(user)

        post = user.create_public_post(text=make_fake_post_text())
        post_comment = user.comment_post(post=post, text=make_fake_post_comment_text())
        post_comment_reply = user.reply_to_comment_for_post(
            post=post, post_comment=post_comment, text=make_fake_post_comment_text()
        )

        data = self._get_create_post_comment_reaction_request_data(ReactionType.HEART)

        url = self._get_url(post=post, post_comment=post_comment_reply)
        response = self.client.put(url, data, **headers)

        self.assertEqual(status.HTTP_201_CREATED, response.status_code)
        self.assertTrue(
            PostCommentReaction.objects.filter(
                post_comment_id=post_comment_reply.pk,
                reaction_type=ReactionType.HEART,
                reactor_id=user.pk,
            ).count()
            == 1
        )

    def test_cannot_react_to_foreign_encircled_post_comment(self):
        """should not be able to react in a foreign encircled post comment and return 400"""
        user = make_user()
        headers = make_authentication_headers_for_user(user)

        foreign_user = make_user()
        circle = make_circle(creator=foreign_user)
        post = foreign_user.create_encircled_post(text=make_fake_post_text(), circles_ids=[circle.pk])
        post_comment = foreign_user.comment_post(post=post, text=make_fake_post_comment_text())

        data = self._get_create_post_comment_reaction_request_data(ReactionType.HEART)

        url = self._get_url(post=post, post_comment=post_comment)
        response = self.client.put(url, data, **headers)

        self.assertEqual(status.HTTP_400_BAD_REQUEST, response.status_code)
        self.assertTrue(
            PostCommentReaction.objects.filter(
                post_comment_id=post_comment.pk,
                reaction_type=ReactionType.HEART,
                reactor_id=user.pk,
            ).count()
            == 0
        )

    def test_can_react_to_connected_user_public_post_comment(self):
        """should be able to react in the public post comment of a connected user post and return 201"""
        user = make_user()
        headers = make_authentication_headers_for_user(user)

        user_to_connect = make_user()

        user.connect_with_user_with_id(user_to_connect.pk)

        connected_user_post = user_to_connect.create_public_post(text=make_fake_post_text())
        connected_user_post_comment = user_to_connect.comment_post(
            post=connected_user_post, text=make_fake_post_comment_text()
        )

        data = self._get_create_post_comment_reaction_request_data(ReactionType.HEART)

        url = self._get_url(post=connected_user_post, post_comment=connected_user_post_comment)
        response = self.client.put(url, data, **headers)

        self.assertEqual(response.status_code, status.HTTP_201_CREATED, f"Response: {response.data}")
        self.assertTrue(
            PostCommentReaction.objects.filter(
                post_comment_id=connected_user_post_comment.pk,
                reaction_type=ReactionType.HEART,
                reactor_id=user.pk,
            ).count()
            == 1
        )

    def test_can_react_to_connected_user_encircled_post_comment_part_of(self):
        """should be able to react in the encircled post comment of a connected user which the user is part of and return 201"""
        user = make_user()
        headers = make_authentication_headers_for_user(user)

        user_to_connect = make_user()
        circle = make_circle(creator=user_to_connect)

        user.connect_with_user_with_id(user_to_connect.pk)
        user_to_connect.confirm_connection_with_user_with_id(user.pk, circles_ids=[circle.pk])

        connected_user_post = user_to_connect.create_encircled_post(
            text=make_fake_post_text(), circles_ids=[circle.pk]
        )
        connected_user_post_comment = user_to_connect.comment_post(
            post=connected_user_post, text=make_fake_post_comment_text()
        )

        data = self._get_create_post_comment_reaction_request_data(ReactionType.HEART)

        url = self._get_url(post=connected_user_post, post_comment=connected_user_post_comment)
        response = self.client.put(url, data, **headers)

        self.assertEqual(response.status_code, status.HTTP_201_CREATED, f"Response: {response.data}")
        self.assertEqual(
            PostCommentReaction.objects.filter(
                post_comment_id=connected_user_post_comment.pk,
                reaction_type=ReactionType.HEART,
                reactor_id=user.pk,
            ).count(),
            1,
        )

    def test_cannot_react_to_connected_user_encircled_post_comment_not_part_of(self):
        """should NOT be able to react in the encircled post comment of a connected user which the user is NOT part of and return 400"""
        user = make_user()
        headers = make_authentication_headers_for_user(user)

        user_to_connect = make_user()
        circle = make_circle(creator=user_to_connect)

        user.connect_with_user_with_id(user_to_connect.pk)
        # Note there is no confirmation of the connection on the other side

        connected_user_post = user_to_connect.create_encircled_post(
            text=make_fake_post_text(), circles_ids=[circle.pk]
        )
        connected_user_post_comment = user_to_connect.comment_post(
            post=connected_user_post, text=make_fake_post_comment_text()
        )

        data = self._get_create_post_comment_reaction_request_data(ReactionType.HEART)

        url = self._get_url(post=connected_user_post, post_comment=connected_user_post_comment)
        response = self.client.put(url, data, **headers)

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST, f"Response: {response.data}")

        self.assertTrue(
            PostCommentReaction.objects.filter(
                post_comment_id=connected_user_post.pk,
                reaction_type=ReactionType.HEART,
                reactor_id=user.pk,
            ).count()
            == 0
        )

    def test_can_react_to_user_public_post_comment(self):
        """should be able to react in the public post comment of any user and return 201"""
        user = make_user()
        headers = make_authentication_headers_for_user(user)

        foreign_user = make_user()

        foreign_user_post = foreign_user.create_public_post(text=make_fake_post_text())
        foreign_user_post_comment = foreign_user.comment_post(
            post=foreign_user_post, text=make_fake_post_comment_text()
        )

        data = self._get_create_post_comment_reaction_request_data(ReactionType.HEART)

        url = self._get_url(post=foreign_user_post, post_comment=foreign_user_post_comment)
        response = self.client.put(url, data, **headers)

        self.assertEqual(response.status_code, status.HTTP_201_CREATED, f"Response: {response.data}")
        self.assertEqual(
            PostCommentReaction.objects.filter(
                post_comment_id=foreign_user_post_comment.pk,
                reaction_type=ReactionType.HEART,
                reactor_id=user.pk,
            ).count(),
            1,
        )

    def test_cannot_react_to_followed_user_encircled_post_comment(self):
        """should be able to react in the encircled post comment of a followed user return 400"""
        user = make_user()
        headers = make_authentication_headers_for_user(user)

        user_to_follow = make_user()
        circle = make_circle(creator=user_to_follow)

        user.follow_user_with_id(user_to_follow.pk)

        followed_user_post = user_to_follow.create_encircled_post(text=make_fake_post_text(), circles_ids=[circle.pk])
        followed_user_post_comment = user_to_follow.comment_post(
            post=followed_user_post, text=make_fake_post_comment_text()
        )

        data = self._get_create_post_comment_reaction_request_data(ReactionType.HEART)

        url = self._get_url(post=followed_user_post, post_comment=followed_user_post_comment)
        response = self.client.put(url, data, **headers)

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST, f"Response: {response.data}")
        self.assertTrue(
            PostCommentReaction.objects.filter(
                post_comment_id=followed_user_post.pk,
                reaction_type=ReactionType.HEART,
                reactor_id=user.pk,
            ).count()
            == 0
        )

    def test_cannot_react_in_post_comment_from_community_banned_from(self):
        """should not be able to react in the post comment of a community banned from and return 400"""
        user = make_user()
        headers = make_authentication_headers_for_user(user)

        community_owner = make_user()
        community = make_community(creator=community_owner)

        user.join_community_with_name(community_name=community.name)

        post = community_owner.create_community_post(community_name=community.name, text=make_fake_post_text())
        post_comment = community_owner.comment_post(post=post, text=make_fake_post_comment_text())

        community_owner.ban_user_with_username_from_community_with_name(
            username=user.username, community_name=community.name
        )

        data = self._get_create_post_comment_reaction_request_data(ReactionType.HEART)

        url = self._get_url(post=post, post_comment=post_comment)
        response = self.client.put(url, data, **headers)

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST, f"Response: {response.data}")

        self.assertTrue(
            PostCommentReaction.objects.filter(
                post_comment_id=post_comment.pk,
                reaction_type=ReactionType.HEART,
                reactor_id=user.pk,
            ).count()
            == 0
        )

    def test_cannot_react_to_closed_community_post_comment_if_not_creator(self):
        """should NOT be able to react in a closed community post comment if not creator"""
        user = make_user()
        admin = make_user()
        community = make_community(admin)
        headers = make_authentication_headers_for_user(user)

        post_creator = make_user()
        post_creator.join_community_with_name(community_name=community.name)
        user.join_community_with_name(community_name=community.name)

        community_post = post_creator.create_community_post(
            community_name=community.name, text=make_fake_post_comment_text()
        )
        community_post_comment = post_creator.comment_post(post=community_post, text=make_fake_post_comment_text())
        community_post.is_closed = True
        community_post.save()

        data = self._get_create_post_comment_reaction_request_data(ReactionType.HEART)

        url = self._get_url(post=community_post, post_comment=community_post_comment)
        response = self.client.put(url, data, **headers)

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST, f"Response: {response.data}")
        self.assertTrue(
            PostCommentReaction.objects.filter(
                post_comment_id=community_post_comment.pk,
                reaction_type=ReactionType.HEART,
                reactor_id=user.pk,
            ).count()
            == 0
        )

    def test_cannot_react_to_closed_community_post_comment_if_creator(self):
        """should NOT be able to react in a closed community post comment if creator"""
        user = make_user()
        admin = make_user()
        community = make_community(admin)

        post_creator = make_user()
        post_creator.join_community_with_name(community_name=community.name)
        user.join_community_with_name(community_name=community.name)

        community_post = post_creator.create_community_post(
            community_name=community.name, text=make_fake_post_comment_text()
        )
        community_post_comment = post_creator.comment_post(post=community_post, text=make_fake_post_comment_text())
        community_post.is_closed = True
        community_post.save()

        data = self._get_create_post_comment_reaction_request_data(ReactionType.HEART)

        headers = make_authentication_headers_for_user(post_creator)
        url = self._get_url(post=community_post, post_comment=community_post_comment)
        response = self.client.put(url, data, **headers)

        self.assertEqual(status.HTTP_400_BAD_REQUEST, response.status_code)
        self.assertTrue(
            PostCommentReaction.objects.filter(
                post_comment_id=community_post_comment.pk,
                reaction_type=ReactionType.HEART,
                reactor_id=post_creator.pk,
            ).count()
            == 0
        )

    def test_cannot_react_to_blocked_user_post_comment(self):
        """should not be able to react to a blocked user post comment and return 400"""
        user = make_user()
        headers = make_authentication_headers_for_user(user)

        user_to_block = make_user()

        user.follow_user_with_id(user_to_block.pk)

        post = user_to_block.create_public_post(text=make_fake_post_text())
        post_comment = user_to_block.comment_post(post=post, text=make_fake_post_comment_text())

        user.block_user_with_id(user_id=user_to_block.pk)

        data = self._get_create_post_comment_reaction_request_data(ReactionType.HEART)

        url = self._get_url(post=post, post_comment=post_comment)
        response = self.client.put(url, data, **headers)

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST, f"Response: {response.data}")
        self.assertTrue(
            PostCommentReaction.objects.filter(
                post_comment_id=post_comment.pk,
                reaction_type=ReactionType.HEART,
                reactor_id=user.pk,
            ).count()
            == 0
        )

    def test_cannot_react_to_blocking_user_post_comment(self):
        """should not be able to react to a blocking user post comment and return 400"""
        user = make_user()
        headers = make_authentication_headers_for_user(user)

        blocking_user = make_user()

        user.follow_user_with_id(blocking_user.pk)

        post = blocking_user.create_public_post(text=make_fake_post_text())

        post_comment = blocking_user.comment_post_with_id(post_id=post.pk, text=make_fake_post_comment_text())

        blocking_user.block_user_with_id(user_id=user.pk)

        data = self._get_create_post_comment_reaction_request_data(ReactionType.HEART)

        url = self._get_url(post=post, post_comment=post_comment)
        response = self.client.put(url, data, **headers)

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST, f"Response: {response.data}")
        self.assertTrue(
            PostCommentReaction.objects.filter(
                post_comment_id=post_comment.pk,
                reaction_type=ReactionType.HEART,
                reactor_id=user.pk,
            ).count()
            == 0
        )

    def test_cannot_react_to_blocked_user_community_post_comment(self):
        """should not be able to react to a blocked user community post comment and return 400"""
        user = make_user()
        headers = make_authentication_headers_for_user(user)

        community_owner = make_user()
        community = make_community(creator=community_owner)

        user_to_block = make_user()

        user_to_block.join_community_with_name(community_name=community.name)

        post = user_to_block.create_community_post(community_name=community.name, text=make_fake_post_text())
        post_comment = user_to_block.comment_post_with_id(post_id=post.pk, text=make_fake_post_comment_text())

        user.block_user_with_id(user_id=user_to_block.pk)

        data = self._get_create_post_comment_reaction_request_data(ReactionType.HEART)

        url = self._get_url(post=post, post_comment=post_comment)
        response = self.client.put(url, data, **headers)

        self.assertEqual(status.HTTP_400_BAD_REQUEST, response.status_code)
        self.assertTrue(
            PostCommentReaction.objects.filter(
                post_comment_id=post_comment.pk,
                reaction_type=ReactionType.HEART,
                reactor_id=user.pk,
            ).count()
            == 0
        )

    def test_cannot_react_to_blocking_user_community_post_comment(self):
        """should not be able to react to a blocking user community post comment and return 400"""
        user = make_user()
        headers = make_authentication_headers_for_user(user)

        community_owner = make_user()
        community = make_community(creator=community_owner)

        blocking_user = make_user()

        blocking_user.join_community_with_name(community_name=community.name)

        post = blocking_user.create_community_post(community_name=community.name, text=make_fake_post_text())

        post_comment = blocking_user.comment_post_with_id(post_id=post.pk, text=make_fake_post_comment_text())

        blocking_user.block_user_with_id(user_id=user.pk)

        data = self._get_create_post_comment_reaction_request_data(ReactionType.HEART)

        url = self._get_url(post=post, post_comment=post_comment)
        response = self.client.put(url, data, **headers)

        self.assertEqual(status.HTTP_400_BAD_REQUEST, response.status_code)
        self.assertTrue(
            PostCommentReaction.objects.filter(
                post_comment_id=post_comment.pk,
                reaction_type=ReactionType.HEART,
                reactor_id=user.pk,
            ).count()
            == 0
        )

    def test_can_react_to_blocked_community_staff_member_post_comment(self):
        """should be able to react to a blocked community staff member post comment and return 201"""
        user = make_user()
        headers = make_authentication_headers_for_user(user)

        community_owner = make_user()
        community = make_community(creator=community_owner)

        post = community_owner.create_community_post(community_name=community.name, text=make_fake_post_text())

        post_comment = community_owner.comment_post_with_id(post_id=post.pk, text=make_fake_post_comment_text())

        user.block_user_with_id(user_id=community_owner.pk)

        data = self._get_create_post_comment_reaction_request_data(ReactionType.HEART)

        url = self._get_url(post=post, post_comment=post_comment)
        response = self.client.put(url, data, **headers)

        self.assertEqual(response.status_code, status.HTTP_201_CREATED, f"Response: {response.data}")
        self.assertTrue(
            PostCommentReaction.objects.filter(
                post_comment_id=post_comment.pk,
                reaction_type=ReactionType.HEART,
                reactor_id=user.pk,
            ).count()
            == 1
        )

    def test_can_react_to_blocking_community_staff_member_post_comment(self):
        """should be able to react to a blocking community staff member post comment and return 201"""
        user = make_user()
        headers = make_authentication_headers_for_user(user)

        community_owner = make_user()
        community = make_community(creator=community_owner)

        post = community_owner.create_community_post(community_name=community.name, text=make_fake_post_text())

        post_comment = user.comment_post_with_id(post_id=post.pk, text=make_fake_post_comment_text())

        community_owner.block_user_with_id(user_id=user.pk)

        data = self._get_create_post_comment_reaction_request_data(ReactionType.HEART)

        url = self._get_url(post=post, post_comment=post_comment)
        response = self.client.put(url, data, **headers)

        self.assertEqual(response.status_code, status.HTTP_201_CREATED, f"Response: {response.data}")
        self.assertTrue(
            PostCommentReaction.objects.filter(
                post_comment_id=post_comment.pk,
                reaction_type=ReactionType.HEART,
                reactor_id=user.pk,
            ).count()
            == 1
        )

    def test_can_react_to_post_comment_only_once(self):
        """should be able to react in own post comment only once, update the old reaction and return 201"""
        user = make_user()
        headers = make_authentication_headers_for_user(user)
        post = user.create_public_post(text=make_fake_post_text())
        post_comment = user.comment_post_with_id(post_id=post.pk, text=make_fake_post_comment_text())

        data = self._get_create_post_comment_reaction_request_data(ReactionType.HEART)

        url = self._get_url(post=post, post_comment=post_comment)
        self.client.put(url, data, **headers)

        data = self._get_create_post_comment_reaction_request_data(ReactionType.HEART)
        response = self.client.put(url, data, **headers)

        self.assertEqual(response.status_code, status.HTTP_201_CREATED, f"Response: {response.data}")
        self.assertTrue(
            PostCommentReaction.objects.filter(post_comment_id=post_comment.pk, reactor_id=user.pk).count() == 1
        )

    def test_reacting_in_foreign_post_comment_creates_notification(self):
        """should create a notification when reacting on a foreign post comment"""
        user = make_user()
        reactor = make_user()

        headers = make_authentication_headers_for_user(reactor)
        post = user.create_public_post(text=make_fake_post_text())
        post_comment = user.comment_post_with_id(post_id=post.pk, text=make_fake_post_comment_text())

        data = self._get_create_post_comment_reaction_request_data(ReactionType.HEART)

        url = self._get_url(post=post, post_comment=post_comment)
        self.client.put(url, data, **headers)

        self.assertTrue(
            PostCommentReactionNotification.objects.filter(
                post_comment_reaction__reaction_type=ReactionType.HEART,
                notification__owner=user,
            ).exists()
        )

    @mock.patch("openbook_notifications.helpers.send_post_comment_reaction_push_notification")
    def test_reacting_on_foreign_post_comment_sends_push_notification(
        self, send_post_comment_reaction_push_notification_call
    ):
        """should send a push notification when  when reacting on a foreign post comment"""
        user = make_user()
        reactor = make_user()

        headers = make_authentication_headers_for_user(reactor)
        post = user.create_public_post(text=make_fake_post_text())
        post_comment = user.comment_post_with_id(post_id=post.pk, text=make_fake_post_comment_text())

        data = self._get_create_post_comment_reaction_request_data(ReactionType.HEART)

        url = self._get_url(post=post, post_comment=post_comment)
        self.client.put(url, data, **headers)

        post_comment_reaction = PostCommentReaction.objects.get(reactor_id=reactor.pk, post_comment_id=post_comment.id)

        send_post_comment_reaction_push_notification_call.assert_called_with(
            post_comment_reaction=post_comment_reaction
        )

    @mock.patch("openbook_notifications.helpers.send_post_comment_reaction_push_notification")
    def test_reacting_on_foreign_post_comment_doesnt_send_push_notification_when_muted(
        self, send_post_comment_reaction_push_notification_call
    ):
        """should NOT send a push notification when reacting on a foreign post comment when muted"""
        user = make_user()
        reactor = make_user()

        headers = make_authentication_headers_for_user(reactor)
        post = user.create_public_post(text=make_fake_post_text())
        post_comment = user.comment_post_with_id(post_id=post.pk, text=make_fake_post_comment_text())
        user.mute_post_comment_with_id(post_comment_id=post_comment.pk)

        data = self._get_create_post_comment_reaction_request_data(ReactionType.HEART)

        url = self._get_url(post=post, post_comment=post_comment)
        self.client.put(url, data, **headers)

        send_post_comment_reaction_push_notification_call.assert_not_called()

    @mock.patch("openbook_notifications.helpers.send_post_comment_reaction_push_notification")
    def test_reacting_on_foreign_post_comment_doesnt_send_push_notification_when_post_muted(
        self, send_post_comment_reaction_push_notification_call
    ):
        """should NOT send a push notification when reacting on a foreign post comment when post muted"""
        user = make_user()
        reactor = make_user()

        headers = make_authentication_headers_for_user(reactor)
        post = user.create_public_post(text=make_fake_post_text())
        post_comment = user.comment_post_with_id(post_id=post.pk, text=make_fake_post_comment_text())
        user.mute_post_with_id(post_id=post.pk)

        data = self._get_create_post_comment_reaction_request_data(ReactionType.HEART)

        url = self._get_url(post=post, post_comment=post_comment)
        self.client.put(url, data, **headers)

        send_post_comment_reaction_push_notification_call.assert_not_called()

    def test_reacting_in_own_post_comment_does_not_create_notification(self):
        """should not create a notification when reacting on an own post comment"""
        user = make_user()

        headers = make_authentication_headers_for_user(user)
        post = user.create_public_post(text=make_fake_post_text())
        post_comment = user.comment_post_with_id(post_id=post.pk, text=make_fake_post_comment_text())

        data = self._get_create_post_comment_reaction_request_data(ReactionType.HEART)

        url = self._get_url(post=post, post_comment=post_comment)
        self.client.put(url, data, **headers)

        self.assertFalse(
            PostCommentReactionNotification.objects.filter(
                post_comment_reaction__reaction_type=ReactionType.HEART,
                notification__owner=user,
            ).exists()
        )

    def _get_create_post_comment_reaction_request_data(self, reaction_type: ReactionType):
        return {
            "reaction_type": reaction_type.value,
        }

    def _get_url(self, post, post_comment):
        return reverse(
            "post-comment-reactions",
            kwargs={
                "post_id": post.id,
                "post_comment_id": post_comment.id,
            },
        )


class PostCommentReactionsEmojiCountAPITests(OpenbookAPITestCase):
    """
    PostCommentReactionsEmojiCountAPI
    """

    fixtures = ["openbook_circles/fixtures/circles.json"]

    def test_can_retrieve_post_comment_reactions_count(self):
        """should be able to retrieve a valid post comment reactions emoji count and return 200"""
        user = make_user()
        headers = make_authentication_headers_for_user(user)
        post = user.create_public_post(text=make_fake_post_text())
        post_comment = user.comment_post_with_id(post_id=post.pk, text=make_fake_post_comment_text())

        reactions_to_react_with = [
            {"reaction_type": ReactionType.HEART.value, "count": 3},
        ]

        reactions = {}

        for reaction in reactions_to_react_with:
            id = reaction.get("reaction_type")
            reactions[str(id)] = reaction

        for reaction in reactions_to_react_with:
            for count in range(reaction["count"]):
                reactor = make_user()
                reactor.react_to_post_comment_with_id(
                    post_comment_id=post_comment.pk,
                    reaction_type=ReactionType.HEART,
                )

        url = self._get_url(post=post, post_comment=post_comment)

        response = self.client.get(url, **headers)

        self.assertEqual(response.status_code, status.HTTP_200_OK, f"Response: {response.data}")

        response_reaction_counts = json.loads(response.content, object_hook=uuid_id_parser)

        self.assertTrue(len(response_reaction_counts), len(reactions_to_react_with))

        for response_reaction_count in response_reaction_counts:
            response_reaction_type = response_reaction_count.get("reaction_type")
            count = response_reaction_count.get("count")
            reaction = reactions[str(response_reaction_type)]
            self.assertIsNotNone(reaction)
            reaction_count = reaction["count"]
            self.assertEqual(count, reaction_count)

    def test_cannot_retrieve_post_comment_reaction_from_blocked_user(self):
        """should not be able to retrieve the post comment reaction from a blocked user"""
        user = make_user()

        post_creator = make_user()
        blocked_user = make_user()

        post = post_creator.create_public_post(text=make_fake_post_text())
        post_comment = user.comment_post_with_id(post_id=post.pk, text=make_fake_post_comment_text())

        blocked_user.react_to_post_comment_with_id(post_comment_id=post_comment.pk, reaction_type=ReactionType.HEART)

        user.block_user_with_id(user_id=blocked_user.pk)

        url = self._get_url(post=post, post_comment=post_comment)

        headers = make_authentication_headers_for_user(user)
        response = self.client.get(url, **headers)

        self.assertEqual(response.status_code, status.HTTP_200_OK, f"Response: {response.data}")

        response_reactions = json.loads(response.content, object_hook=uuid_id_parser)

        self.assertEqual(len(response_reactions), 0)

    def test_cannot_retrieve_post_comment_reactions_from_blocking_user(self):
        """should not be able to retrieve the post comment reactions from a blocking user"""
        user = make_user()

        post_creator = make_user()
        blocking_user = make_user()

        post = post_creator.create_public_post(text=make_fake_post_text())
        post_comment = user.comment_post_with_id(post_id=post.pk, text=make_fake_post_comment_text())

        blocking_user.react_to_post_comment_with_id(post_comment_id=post_comment.pk, reaction_type=ReactionType.HEART)

        blocking_user.block_user_with_id(user_id=user.pk)

        url = self._get_url(post=post, post_comment=post_comment)

        headers = make_authentication_headers_for_user(user)
        response = self.client.get(url, **headers)

        self.assertEqual(response.status_code, status.HTTP_200_OK, f"Response: {response.data}")

        response_reactions = json.loads(response.content, object_hook=uuid_id_parser)

        self.assertEqual(len(response_reactions), 0)

    def test_cannot_retrieve_post_comment_reactions_from_blocked_user_in_a_community(
        self,
    ):
        """should not be able to retrieve the post comment reactions from a blocked user in a community"""
        user = make_user()

        post_creator = make_user()
        community = make_community(creator=post_creator)

        blocked_user = make_user()

        post = post_creator.create_community_post(text=make_fake_post_text(), community_name=community.name)
        post_comment = post_creator.comment_post_with_id(post_id=post.pk, text=make_fake_post_comment_text())

        blocked_user.react_to_post_comment_with_id(post_comment_id=post_comment.pk, reaction_type=ReactionType.HEART)

        user.block_user_with_id(user_id=blocked_user.pk)

        url = self._get_url(post=post, post_comment=post_comment)

        headers = make_authentication_headers_for_user(user)
        response = self.client.get(url, **headers)

        self.assertEqual(response.status_code, status.HTTP_200_OK, f"Response: {response.data}")

        response_reactions = json.loads(response.content, object_hook=uuid_id_parser)

        self.assertEqual(len(response_reactions), 0)

    def test_cannot_retrieve_post_comment_reactions_from_blocking_user_in_a_community(
        self,
    ):
        """should not be able to retrieve the post comment reactions from a blocking user in a community"""
        user = make_user()

        post_creator = make_user()
        community = make_community(creator=post_creator)

        blocking_user = make_user()

        post = post_creator.create_community_post(text=make_fake_post_text(), community_name=community.name)
        post_comment = post_creator.comment_post_with_id(post_id=post.pk, text=make_fake_post_comment_text())

        blocking_user.react_to_post_comment_with_id(post_comment_id=post_comment.pk, reaction_type=ReactionType.HEART)

        blocking_user.block_user_with_id(user_id=user.pk)

        url = self._get_url(post=post, post_comment=post_comment)

        headers = make_authentication_headers_for_user(user)
        response = self.client.get(url, **headers)

        self.assertEqual(response.status_code, status.HTTP_200_OK, f"Response: {response.data}")

        response_reactions = json.loads(response.content, object_hook=uuid_id_parser)

        self.assertEqual(len(response_reactions), 0)

    def test_can_retrieve_post_comment_reactions_from_blocked_user_in_a_community_if_staff(
        self,
    ):
        """should be able to retrieve the post comment reactions from a blocked user in a community if staff member"""
        user = make_user()
        community = make_community(creator=user)
        post_creator = make_user()
        blocked_user = make_user()

        post_creator.join_community_with_name(community_name=community.name)

        post = post_creator.create_community_post(text=make_fake_post_text(), community_name=community.name)
        post_comment = post_creator.comment_post_with_id(post_id=post.pk, text=make_fake_post_comment_text())

        blocked_user.react_to_post_comment_with_id(post_comment_id=post_comment.pk, reaction_type=ReactionType.HEART)

        user.block_user_with_id(user_id=blocked_user.pk)

        url = self._get_url(post=post, post_comment=post_comment)

        headers = make_authentication_headers_for_user(user)
        response = self.client.get(url, **headers)

        self.assertEqual(response.status_code, status.HTTP_200_OK, f"Response: {response.data}")

        response_reactions_counts = json.loads(response.content, object_hook=uuid_id_parser)

        self.assertEqual(1, len(response_reactions_counts))

        response_reaction_count = response_reactions_counts[0]

        response_type = response_reaction_count.get("reaction_type")
        response_reaction_count = response_reaction_count.get("count")

        self.assertEqual(response_type, ReactionType.HEART)
        self.assertEqual(1, response_reaction_count)

    def test_can_retrieve_post_comment_reactions_from_blocking_user_in_a_community_if_staff(
        self,
    ):
        """should be able to retrieve the post comment reactions from a blocking user in a community if staff member"""
        user = make_user()
        community = make_community(creator=user)
        post_creator = make_user()
        blocking_user = make_user()

        post_creator.join_community_with_name(community_name=community.name)

        post = post_creator.create_community_post(text=make_fake_post_text(), community_name=community.name)
        post_comment = post_creator.comment_post_with_id(post_id=post.pk, text=make_fake_post_comment_text())

        blocking_user.react_to_post_comment_with_id(post_comment_id=post_comment.pk, reaction_type=ReactionType.HEART)

        blocking_user.block_user_with_id(user_id=user.pk)

        url = self._get_url(post=post, post_comment=post_comment)

        headers = make_authentication_headers_for_user(user)
        response = self.client.get(url, **headers)

        self.assertEqual(response.status_code, status.HTTP_200_OK, f"Response: {response.data}")

        response_reaction_counts = json.loads(response.content, object_hook=uuid_id_parser)

        self.assertEqual(1, len(response_reaction_counts))

        response_reaction_count = response_reaction_counts[0]

        response_reaction_type = response_reaction_count.get("reaction_type")
        response_reaction_count = response_reaction_count.get("count")

        self.assertEqual(response_reaction_type, ReactionType.HEART)
        self.assertEqual(1, response_reaction_count)

    def _get_url(self, post, post_comment):
        return reverse(
            "post-comment-reactions-emoji-count",
            kwargs={"post_id": post.id, "post_comment_id": post_comment.pk},
        )
