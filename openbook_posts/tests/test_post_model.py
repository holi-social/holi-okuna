from django.test import TestCase
from rest_framework.exceptions import ValidationError

from openbook_circles.models import Circle
from openbook_common.tests.assertions import TestAssertionsMixin
from openbook_common.tests.helpers import make_user, make_community, make_fake_post_text, make_fake_post_title
from openbook_common.utils.model_loaders import get_post_model


class PostModelTest(TestAssertionsMixin, TestCase):
    fixtures = ["openbook_circles/fixtures/circles.json", "openbook_moderation/fixtures/moderation_categories.json"]

    def test_create_post_success(self):
        space_creator = make_user()
        space = make_community(creator=space_creator)

        post_text = make_fake_post_text()
        post_title = make_fake_post_title()
        world_circle_id = Circle.get_world_circle_id()

        Post = get_post_model()
        post = Post.create_post(
            creator=space_creator,
            text=post_text,
            title=post_title,
            circles_ids=[world_circle_id],
            community_id=space.id,
        )
        self.assertEqual(space.posts.count(), 1)
        self.assertEqual(post.community.id, space.id)
        self.assertEqual(post.text, post_text)
        self.assertEqual(post.title, post_title)
        self.assertIn(world_circle_id, post.circles.values_list("id", flat=True))

    def test_create_post_error_community_and_circle_missing(self):
        space_creator = make_user()
        space = make_community(creator=space_creator)

        post_text = make_fake_post_text()
        post_title = make_fake_post_title()

        Post = get_post_model()

        with self.assertRaises(ValidationError):
            Post.create_post(creator=space_creator, text=post_text, title=post_title)

        self.assertEqual(space.posts.count(), 0)
