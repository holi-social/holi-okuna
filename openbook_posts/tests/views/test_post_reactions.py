# Create your tests here.
import json
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
    make_reactions_emoji_group,
    make_community,
)
from openbook_common.types import ReactionType
from openbook_common.utils.test import uuid_id_parser
from openbook_notifications.models import PostReactionNotification
from openbook_posts.models import PostReaction

logger = logging.getLogger(__name__)
fake = Faker()


class PostReactionsAPITests(OpenbookAPITestCase):
    """
    PostReactionsAPI
    """

    fixtures = ["openbook_circles/fixtures/circles.json"]

    def test_can_react_to_own_post(self):
        """should be able to reaction in own post and return 201"""
        user = make_user()
        headers = make_authentication_headers_for_user(user)
        post = user.create_public_post(text=make_fake_post_text())

        data = self._get_create_post_reaction_request_data(ReactionType.HEART)

        url = self._get_url(post)
        response = self.client.put(url, data, **headers)

        self.assertEqual(response.status_code, status.HTTP_201_CREATED, f"Response: {response.data}")
        self.assertTrue(
            PostReaction.objects.filter(post_id=post.pk, reaction_type=ReactionType.HEART, reactor_id=user.pk).count()
            == 1
        )

    def test_cannot_react_to_foreign_post(self):
        """should not be able to reaction in a foreign encircled post and return 400"""
        user = make_user()
        headers = make_authentication_headers_for_user(user)

        foreign_user = make_user()
        circle = make_circle(creator=foreign_user)
        post = foreign_user.create_encircled_post(text=make_fake_post_text(), circles_ids=[circle.pk])

        data = self._get_create_post_reaction_request_data(ReactionType.HEART)

        url = self._get_url(post)
        response = self.client.put(url, data, **headers)

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST, f"Response: {response.data}")
        self.assertTrue(
            PostReaction.objects.filter(post_id=post.pk, reaction_type=ReactionType.HEART, reactor_id=user.pk).count()
            == 0
        )

    def test_can_react_to_connected_user_public_post(self):
        """should be able to reaction in the public post of a connected user post and return 201"""
        user = make_user()
        headers = make_authentication_headers_for_user(user)

        user_to_connect = make_user()

        user.connect_with_user_with_id(user_to_connect.pk)

        connected_user_post = user_to_connect.create_public_post(text=make_fake_post_text())

        data = self._get_create_post_reaction_request_data(ReactionType.HEART)

        url = self._get_url(connected_user_post)
        response = self.client.put(url, data, **headers)

        self.assertEqual(response.status_code, status.HTTP_201_CREATED, f"Response: {response.data}")
        self.assertTrue(
            PostReaction.objects.filter(
                post_id=connected_user_post.pk,
                reaction_type=ReactionType.HEART,
                reactor_id=user.pk,
            ).count()
            == 1
        )

    def test_can_react_to_connected_user_encircled_post_part_of(self):
        """should be able to reaction in the encircled post of a connected user which the user is part of and return 201"""
        user = make_user()
        headers = make_authentication_headers_for_user(user)

        user_to_connect = make_user()
        circle = make_circle(creator=user_to_connect)

        user.connect_with_user_with_id(user_to_connect.pk)
        user_to_connect.confirm_connection_with_user_with_id(user.pk, circles_ids=[circle.pk])

        connected_user_post = user_to_connect.create_encircled_post(
            text=make_fake_post_text(), circles_ids=[circle.pk]
        )

        data = self._get_create_post_reaction_request_data(ReactionType.HEART)

        url = self._get_url(connected_user_post)
        response = self.client.put(url, data, **headers)

        self.assertEqual(response.status_code, status.HTTP_201_CREATED, f"Response: {response.data}")
        self.assertTrue(
            PostReaction.objects.filter(
                post_id=connected_user_post.pk,
                reaction_type=ReactionType.HEART,
                reactor_id=user.pk,
            ).count()
            == 1
        )

    def test_cannot_react_to_connected_user_encircled_post_not_part_of(self):
        """should NOT be able to reaction in the encircled post of a connected user which the user is NOT part of and return 400"""
        user = make_user()
        headers = make_authentication_headers_for_user(user)

        user_to_connect = make_user()
        circle = make_circle(creator=user_to_connect)

        user.connect_with_user_with_id(user_to_connect.pk)
        # Note there is no confirmation of the connection on the other side

        connected_user_post = user_to_connect.create_encircled_post(
            text=make_fake_post_text(), circles_ids=[circle.pk]
        )

        data = self._get_create_post_reaction_request_data(ReactionType.HEART)

        url = self._get_url(connected_user_post)
        response = self.client.put(url, data, **headers)

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST, f"Response: {response.data}")

        self.assertTrue(
            PostReaction.objects.filter(
                post_id=connected_user_post.pk,
                reaction_type=ReactionType.HEART,
                reactor_id=user.pk,
            ).count()
            == 0
        )

    def test_can_react_to_user_public_post(self):
        """should be able to reaction in the public post of any user and return 201"""
        user = make_user()
        headers = make_authentication_headers_for_user(user)

        foreign_user = make_user()

        foreign_user_post = foreign_user.create_public_post(text=make_fake_post_text())

        data = self._get_create_post_reaction_request_data(ReactionType.HEART)

        url = self._get_url(foreign_user_post)
        response = self.client.put(url, data, **headers)

        self.assertEqual(response.status_code, status.HTTP_201_CREATED, f"Response: {response.data}")
        self.assertTrue(
            PostReaction.objects.filter(
                post_id=foreign_user_post.pk,
                reaction_type=ReactionType.HEART,
                reactor_id=user.pk,
            ).count()
            == 1
        )

    def test_cannot_react_to_followed_user_encircled_post(self):
        """should be able to reaction in the encircled post of a followed user return 400"""
        user = make_user()
        headers = make_authentication_headers_for_user(user)

        user_to_follow = make_user()
        circle = make_circle(creator=user_to_follow)

        user.follow_user_with_id(user_to_follow.pk)

        followed_user_post = user_to_follow.create_encircled_post(text=make_fake_post_text(), circles_ids=[circle.pk])

        data = self._get_create_post_reaction_request_data(ReactionType.HEART)

        url = self._get_url(followed_user_post)
        response = self.client.put(url, data, **headers)

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST, f"Response: {response.data}")
        self.assertTrue(
            PostReaction.objects.filter(
                post_id=followed_user_post.pk,
                reaction_type=ReactionType.HEART,
                reactor_id=user.pk,
            ).count()
            == 0
        )

    def test_cannot_react_in_post_from_community_banned_from(self):
        """should not be able to react in the post of a community banned from and return 400"""
        user = make_user()
        headers = make_authentication_headers_for_user(user)

        community_owner = make_user()
        community = make_community(creator=community_owner)

        user.join_community_with_name(community_name=community.name)

        post = community_owner.create_community_post(community_name=community.name, text=make_fake_post_text())

        community_owner.ban_user_with_username_from_community_with_name(
            username=user.username, community_name=community.name
        )

        data = self._get_create_post_reaction_request_data(ReactionType.HEART)

        url = self._get_url(post)
        response = self.client.put(url, data, **headers)

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST, f"Response: {response.data}")

        self.assertTrue(
            PostReaction.objects.filter(post_id=post.pk, reaction_type=ReactionType.HEART, reactor_id=user.pk).count()
            == 0
        )

    def test_cannot_react_to_closed_community_post_if_not_creator(self):
        """should NOT be able to react in a closed community post if not creator"""
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
        community_post.is_closed = True
        community_post.save()

        data = self._get_create_post_reaction_request_data(ReactionType.HEART)

        url = self._get_url(community_post)
        response = self.client.put(url, data, **headers)

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST, f"Response: {response.data}")
        self.assertTrue(
            PostReaction.objects.filter(
                post_id=community_post.pk,
                reaction_type=ReactionType.HEART,
                reactor_id=user.pk,
            ).count()
            == 0
        )

    def test_can_react_to_closed_community_post_if_creator(self):
        """should be able to react in a closed community post if creator"""
        user = make_user()
        admin = make_user()
        community = make_community(admin)

        post_creator = make_user()
        post_creator.join_community_with_name(community_name=community.name)
        user.join_community_with_name(community_name=community.name)

        community_post = post_creator.create_community_post(
            community_name=community.name, text=make_fake_post_comment_text()
        )
        community_post.is_closed = True
        community_post.save()

        data = self._get_create_post_reaction_request_data(ReactionType.HEART)

        headers = make_authentication_headers_for_user(post_creator)
        url = self._get_url(community_post)
        response = self.client.put(url, data, **headers)

        self.assertEqual(response.status_code, status.HTTP_201_CREATED, f"Response: {response.data}")
        self.assertTrue(
            PostReaction.objects.filter(
                post_id=community_post.pk,
                reaction_type=ReactionType.HEART,
                reactor_id=post_creator.pk,
            ).count()
            == 1
        )

    def test_cannot_react_to_blocked_user_post(self):
        """should not be able to react to a blocked user post and return 400"""
        user = make_user()
        headers = make_authentication_headers_for_user(user)

        user_to_block = make_user()

        user.follow_user_with_id(user_to_block.pk)

        post = user_to_block.create_public_post(text=make_fake_post_text())

        user.comment_post_with_id(post_id=post.pk, text=make_fake_post_comment_text())

        user.block_user_with_id(user_id=user_to_block.pk)

        data = self._get_create_post_reaction_request_data(ReactionType.HEART)

        url = self._get_url(post)
        response = self.client.put(url, data, **headers)

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST, f"Response: {response.data}")
        self.assertTrue(
            PostReaction.objects.filter(post_id=post.pk, reaction_type=ReactionType.HEART, reactor_id=user.pk).count()
            == 0
        )

    def test_cannot_react_to_blocking_user_post(self):
        """should not be able to react to a blocking user post and return 400"""
        user = make_user()
        headers = make_authentication_headers_for_user(user)

        user_to_block = make_user()

        user.follow_user_with_id(user_to_block.pk)

        post = user_to_block.create_public_post(text=make_fake_post_text())

        user.comment_post_with_id(post_id=post.pk, text=make_fake_post_comment_text())

        user_to_block.block_user_with_id(user_id=user.pk)

        data = self._get_create_post_reaction_request_data(ReactionType.HEART)

        url = self._get_url(post)
        response = self.client.put(url, data, **headers)

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST, f"Response: {response.data}")
        self.assertTrue(
            PostReaction.objects.filter(post_id=post.pk, reaction_type=ReactionType.HEART, reactor_id=user.pk).count()
            == 0
        )

    def test_cannot_react_to_blocked_user_community_post(self):
        """should not be able to react to a blocked user community post and return 400"""
        user = make_user()
        headers = make_authentication_headers_for_user(user)

        community_owner = make_user()
        community = make_community(creator=community_owner)

        user_to_block = make_user()

        user_to_block.join_community_with_name(community_name=community.name)

        post = user_to_block.create_community_post(community_name=community.name, text=make_fake_post_text())

        user.comment_post_with_id(post_id=post.pk, text=make_fake_post_comment_text())

        user.block_user_with_id(user_id=user_to_block.pk)

        data = self._get_create_post_reaction_request_data(ReactionType.HEART)

        url = self._get_url(post)
        response = self.client.put(url, data, **headers)

        self.assertEqual(status.HTTP_400_BAD_REQUEST, response.status_code)
        self.assertTrue(
            PostReaction.objects.filter(post_id=post.pk, reaction_type=ReactionType.HEART, reactor_id=user.pk).count()
            == 0
        )

    def test_cannot_react_to_blocking_user_community_post(self):
        """should not be able to react to a blocking user community post and return 400"""
        user = make_user()
        headers = make_authentication_headers_for_user(user)

        community_owner = make_user()
        community = make_community(creator=community_owner)

        user_to_block = make_user()

        user_to_block.join_community_with_name(community_name=community.name)

        post = user_to_block.create_community_post(community_name=community.name, text=make_fake_post_text())

        user.comment_post_with_id(post_id=post.pk, text=make_fake_post_comment_text())

        user_to_block.block_user_with_id(user_id=user.pk)

        data = self._get_create_post_reaction_request_data(ReactionType.HEART)

        url = self._get_url(post)
        response = self.client.put(url, data, **headers)

        self.assertEqual(status.HTTP_400_BAD_REQUEST, response.status_code)
        self.assertTrue(
            PostReaction.objects.filter(post_id=post.pk, reaction_type=ReactionType.HEART, reactor_id=user.pk).count()
            == 0
        )

    def test_can_react_to_blocked_community_staff_member_post(self):
        """should be able to react to a blocked community staff member post and return 201"""
        user = make_user()
        headers = make_authentication_headers_for_user(user)

        community_owner = make_user()
        community = make_community(creator=community_owner)

        post = community_owner.create_community_post(community_name=community.name, text=make_fake_post_text())

        user.comment_post_with_id(post_id=post.pk, text=make_fake_post_comment_text())

        user.block_user_with_id(user_id=community_owner.pk)

        data = self._get_create_post_reaction_request_data(ReactionType.HEART)

        url = self._get_url(post)
        response = self.client.put(url, data, **headers)

        self.assertEqual(response.status_code, status.HTTP_201_CREATED, f"Response: {response.data}")
        self.assertTrue(
            PostReaction.objects.filter(post_id=post.pk, reaction_type=ReactionType.HEART, reactor_id=user.pk).count()
            == 1
        )

    def test_can_react_to_blocking_community_staff_member_post(self):
        """should be able to react to a blocking community staff member post and return 201"""
        user = make_user()
        headers = make_authentication_headers_for_user(user)

        community_owner = make_user()
        community = make_community(creator=community_owner)

        post = community_owner.create_community_post(community_name=community.name, text=make_fake_post_text())

        user.comment_post_with_id(post_id=post.pk, text=make_fake_post_comment_text())

        community_owner.block_user_with_id(user_id=user.pk)

        data = self._get_create_post_reaction_request_data(ReactionType.HEART)

        url = self._get_url(post)
        response = self.client.put(url, data, **headers)

        self.assertEqual(response.status_code, status.HTTP_201_CREATED, f"Response: {response.data}")
        self.assertTrue(
            PostReaction.objects.filter(post_id=post.pk, reaction_type=ReactionType.HEART, reactor_id=user.pk).count()
            == 1
        )

    def test_can_react_to_post_only_once(self):
        """should be able to reaction in own post only once, update the old reaction and return 201"""
        user = make_user()
        headers = make_authentication_headers_for_user(user)
        post = user.create_public_post(text=make_fake_post_text())

        data = self._get_create_post_reaction_request_data(ReactionType.HEART)

        url = self._get_url(post)
        self.client.put(url, data, **headers)

        data = self._get_create_post_reaction_request_data(ReactionType.HEART)
        response = self.client.put(url, data, **headers)

        self.assertEqual(response.status_code, status.HTTP_201_CREATED, f"Response: {response.data}")
        self.assertTrue(PostReaction.objects.filter(post_id=post.pk, reactor_id=user.pk).count() == 1)

    def test_reacting_in_foreign_post_creates_notification(self):
        """should create a notification when reacting on a foreign post"""
        user = make_user()
        reactor = make_user()

        headers = make_authentication_headers_for_user(reactor)
        post = user.create_public_post(text=make_fake_post_text())

        data = self._get_create_post_reaction_request_data(ReactionType.HEART)

        url = self._get_url(post)
        self.client.put(url, data, **headers)

        self.assertTrue(
            PostReactionNotification.objects.filter(
                post_reaction__reaction_type=ReactionType.HEART,
                notification__owner=user,
            ).exists()
        )

    def test_reacting_in_own_post_does_not_create_notification(self):
        """should not create a notification when reacting on an own post"""
        user = make_user()

        headers = make_authentication_headers_for_user(user)
        post = user.create_public_post(text=make_fake_post_text())

        data = self._get_create_post_reaction_request_data(ReactionType.HEART)

        url = self._get_url(post)
        self.client.put(url, data, **headers)

        self.assertFalse(
            PostReactionNotification.objects.filter(
                post_reaction__reaction_type=ReactionType.HEART,
                notification__owner=user,
            ).exists()
        )

    def _get_create_post_reaction_request_data(self, reaction_type):
        return {"reaction_type": reaction_type.value}

    def _get_url(self, post):
        return reverse(
            "post-reactions",
            kwargs={
                "post_id": post.id,
            },
        )


class PostReactionsEmojiCountAPITests(OpenbookAPITestCase):
    """
    PostReactionsEmojiCountAPI
    """

    fixtures = ["openbook_circles/fixtures/circles.json"]

    def test_can_retrieve_reactions_count(self):
        """should be able to retrieve a valid reactions emoji count and return 200"""
        user = make_user()
        headers = make_authentication_headers_for_user(user)
        post = user.create_public_post(text=make_fake_post_text())

        reaction_types_to_react_with = [
            {"reaction_type": ReactionType.HEART.value, "count": 3},
        ]

        reactions = {}

        for reaction in reaction_types_to_react_with:
            id = reaction.get("reaction_type")
            reactions[str(id)] = reaction

        for reaction in reaction_types_to_react_with:
            for count in range(reaction["count"]):
                reactor = make_user()
                reactor.react_to_post_with_id(
                    post_id=post.pk,
                    reaction_type=reaction.get("reaction_type"),
                )

        url = self._get_url(post)

        response = self.client.get(url, **headers)

        self.assertEqual(response.status_code, status.HTTP_200_OK, f"Response: {response.data}")

        response_reaction_counts = json.loads(response.content, object_hook=uuid_id_parser)

        self.assertTrue(len(response_reaction_counts), len(reaction_types_to_react_with))

        for response_reaction_count in response_reaction_counts:
            response_reaction_type = response_reaction_count.get("reaction_type")
            count = response_reaction_count.get("count")
            reaction = reactions[str(response_reaction_type)]
            self.assertIsNotNone(reaction)
            reaction_count = reaction["count"]
            self.assertEqual(count, reaction_count)

    def test_cannot_retrieve_reaction_from_blocked_user(self):
        """should not be able to retrieve the reaction from a blocked user"""
        user = make_user()

        post_creator = make_user()
        blocked_user = make_user()

        post = post_creator.create_public_post(text=make_fake_post_text())

        blocked_user.react_to_post_with_id(
            post_id=post.pk,
            reaction_type=ReactionType.HEART,
        )

        user.block_user_with_id(user_id=blocked_user.pk)

        url = self._get_url(post)

        headers = make_authentication_headers_for_user(user)
        response = self.client.get(url, **headers)

        self.assertEqual(response.status_code, status.HTTP_200_OK, f"Response: {response.data}")

        response_reactions = json.loads(response.content, object_hook=uuid_id_parser)

        self.assertEqual(len(response_reactions), 0)

    def test_cannot_retrieve_reactions_from_blocking_user(self):
        """should not be able to retrieve the reactions from a blocking user"""
        user = make_user()

        post_creator = make_user()
        blocking_user = make_user()

        post = post_creator.create_public_post(text=make_fake_post_text())

        blocking_user.react_to_post_with_id(post_id=post.pk, reaction_type=ReactionType.HEART)

        blocking_user.block_user_with_id(user_id=user.pk)

        url = self._get_url(post)

        headers = make_authentication_headers_for_user(user)
        response = self.client.get(url, **headers)

        self.assertEqual(response.status_code, status.HTTP_200_OK, f"Response: {response.data}")

        response_reactions = json.loads(response.content, object_hook=uuid_id_parser)

        self.assertEqual(len(response_reactions), 0)

    def test_cannot_retrieve_reactions_from_blocked_user_in_a_community(self):
        """should not be able to retrieve the reactions from a blocked user in a community"""
        user = make_user()

        post_creator = make_user()
        community = make_community(creator=post_creator)

        blocked_user = make_user()

        post = post_creator.create_community_post(text=make_fake_post_text(), community_name=community.name)

        blocked_user.react_to_post_with_id(post_id=post.pk, reaction_type=ReactionType.HEART)

        user.block_user_with_id(user_id=blocked_user.pk)

        url = self._get_url(post)

        headers = make_authentication_headers_for_user(user)
        response = self.client.get(url, **headers)

        self.assertEqual(response.status_code, status.HTTP_200_OK, f"Response: {response.data}")

        response_reactions = json.loads(response.content, object_hook=uuid_id_parser)

        self.assertEqual(len(response_reactions), 0)

    def test_cannot_retrieve_reactions_from_blocking_user_in_a_community(self):
        """should not be able to retrieve the reactions from a blocking user in a community"""
        user = make_user()

        post_creator = make_user()
        community = make_community(creator=post_creator)

        blocking_user = make_user()

        post = post_creator.create_community_post(text=make_fake_post_text(), community_name=community.name)

        blocking_user.react_to_post_with_id(post_id=post.pk, reaction_type=ReactionType.HEART)

        blocking_user.block_user_with_id(user_id=user.pk)

        url = self._get_url(post)

        headers = make_authentication_headers_for_user(user)
        response = self.client.get(url, **headers)

        self.assertEqual(response.status_code, status.HTTP_200_OK, f"Response: {response.data}")

        response_reactions = json.loads(response.content, object_hook=uuid_id_parser)

        self.assertEqual(len(response_reactions), 0)

    def test_can_retrieve_reactions_from_blocked_user_in_a_community_if_staff(self):
        """should be able to retrieve the reactions from a blocked user in a community if staff member"""
        user = make_user()
        community = make_community(creator=user)
        post_creator = make_user()
        blocked_user = make_user()

        post_creator.join_community_with_name(community_name=community.name)

        post = post_creator.create_community_post(text=make_fake_post_text(), community_name=community.name)

        blocked_user.react_to_post_with_id(post_id=post.pk, reaction_type=ReactionType.HEART)

        user.block_user_with_id(user_id=blocked_user.pk)

        url = self._get_url(post)

        headers = make_authentication_headers_for_user(user)
        response = self.client.get(url, **headers)

        self.assertEqual(response.status_code, status.HTTP_200_OK, f"Response: {response.data}")

        response_reactions_counts = json.loads(response.content, object_hook=uuid_id_parser)

        self.assertEqual(1, len(response_reactions_counts))

        response_reaction_count = response_reactions_counts[0]

        response_reaction_type = response_reaction_count.get("reaction_type")
        response_reaction_count = response_reaction_count.get("count")

        self.assertEqual(response_reaction_type, ReactionType.HEART)
        self.assertEqual(1, response_reaction_count)

    def test_can_retrieve_reactions_from_blocking_user_in_a_community_if_staff(self):
        """should be able to retrieve the reactions from a blocking user in a community if staff member"""
        user = make_user()
        community = make_community(creator=user)
        post_creator = make_user()
        blocking_user = make_user()

        post_creator.join_community_with_name(community_name=community.name)

        post = post_creator.create_community_post(text=make_fake_post_text(), community_name=community.name)

        blocking_user.react_to_post_with_id(post_id=post.pk, reaction_type=ReactionType.HEART)

        blocking_user.block_user_with_id(user_id=user.pk)

        url = self._get_url(post)

        headers = make_authentication_headers_for_user(user)
        response = self.client.get(url, **headers)

        self.assertEqual(response.status_code, status.HTTP_200_OK, f"Response: {response.data}")

        response_reaction_counts = json.loads(response.content, object_hook=uuid_id_parser)

        self.assertEqual(1, len(response_reaction_counts))

        response_reaction_count = response_reaction_counts[0]

        response_reaction_type = response_reaction_count.get("reaction_type")
        response_reaction_count = response_reaction_count.get("count")

        self.assertEqual(response_reaction_type, ReactionType.HEART.value)
        self.assertEqual(1, response_reaction_count)

    def _get_url(self, post):
        return reverse("post-reactions-emoji-count", kwargs={"post_id": post.id})
