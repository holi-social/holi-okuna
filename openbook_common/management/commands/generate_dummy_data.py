# ruff: noqa: T201
# ruff: noqa: S311
import io
import random
import sys
from contextlib import contextmanager
from urllib import request
from typing import get_args
from django.contrib.auth.backends import UserModel
from django.core.files.uploadedfile import InMemoryUploadedFile
from django.core.management import BaseCommand, CommandError
from django.utils.timezone import now
from faker import Faker

from feed_posts.enums import VisibilityLevel
from feed_posts.models import FeedPost
from openbook import settings
from openbook_auth.events import publish_user_name_updated_event
from openbook_auth.models import User
from openbook_auth.tasks import generate_identity_when_needed
from openbook_common.tests.helpers import (
    make_community_title,
    make_fake_post_title,
    make_users,
)
from openbook_common.enums import ReactionType, VisibilityType
from openbook_common.topics import TopicV2
from openbook_communities.models import Community, Task
from openbook_insights.models import Insight, Discussion
from openbook_polls.models import Poll, Choice
from openbook_posts.models import Post
from openbook_terms.models import FeedPostCategory

from unittest import mock

fake = Faker()
prefix = "generate_"

NO_USERS_AVAILABLE = "no users available, please generate users first"
NO_POSTS_AVAILABLE = "no posts available, please generate posts first"
NO_TOPICS_AVAILABLE = "no topics available, please generate topics first (via loaddata)"


@contextmanager
def image_fetcher(url=f"{settings.IMAGEKIT_URL}/tr:w-300,h-300/default-image.jpg"):
    with request.urlopen(url) as response:  # noqa: S310
        with io.BytesIO(response.read()) as image_io:
            in_memory_file = InMemoryUploadedFile(
                image_io, "ImageField", "image.jpg", "JPEG", sys.getsizeof(image_io), None
            )
            yield in_memory_file


class Command(BaseCommand):
    """
    creating a method that starts with the prefix (see above) automatically adds a new generator to this command.
    """

    help = """Generate dummy data. Check help options for the type of objects that can be created, like --user, --post, ..."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        mock.patch("openbook_notifications.services.NotificationsService", spec=True).start()
        mock.patch("openbook_auth.tasks.update_ory_user_identity").start()
        mock.patch("openbook_auth.tasks.update_ory").start()
        mock.patch("openbook_auth.tasks.update_ory_user_names").start()

    def add_arguments(self, parser):
        for g in [key[len(prefix) :] for key in dir(Command) if key.startswith(prefix)]:
            parser.add_argument(f"--{g}", nargs=1, type=int)

    def handle(self, *args, **options):
        # order is important here, there is dependencies. luckily, reverse order currently fulfills all dependencies
        for key, value in options.items().__reversed__():
            if hasattr(self, prefix + key) and value:
                fn = getattr(self, prefix + key)
                fn(value[0])

    @staticmethod
    def _get_random_users(nr_of_users):
        return User.objects.filter(UserModel.is_visible_ignore_blocked_query()).all()[: max(10, nr_of_users)]

    @staticmethod
    def _get_random_space():
        return random.choice(Community.objects.all())

    @staticmethod
    def _generate_reactions(obj, users):
        for user in users:
            if random.choice([False, True]):
                obj.react(user, random.choice([_ for _ in ReactionType]))

    @staticmethod
    def generate_users(nr):
        print(f"generate {nr} users")
        users = make_users(nr)
        for user in users:
            generate_identity_when_needed(user)
            publish_user_name_updated_event(user=user)

    def generate_feed_posts(self, nr):
        print(f"generate {nr} feed posts with comments")
        users = self._get_random_users(int(nr / 1.5))
        if not users:
            raise CommandError(NO_USERS_AVAILABLE)
        for _ in range(nr):
            with image_fetcher() as image_file:
                user = random.choice(users)
                category = FeedPostCategory.objects.get(slug="topic-for-conversation")
                feed_post = FeedPost.objects.create(
                    title=make_fake_post_title(),
                    visibility=VisibilityLevel.PUBLIC,
                    description=fake.text(max_nb_chars=100),
                    image=image_file,
                    category=category,
                    creator=user,
                )
                comment_count = random.randint(1, 5)
                for _ in range(comment_count):
                    feed_post.comment_on(random.choice(users), fake.text(max_nb_chars=300), language="en")

    def generate_space_updates(self, nr):
        print(f"generate {nr} space updates with comments and reactions")
        users = self._get_random_users(int(nr / 1.5))
        if not users:
            raise CommandError(NO_USERS_AVAILABLE)
        for _ in range(nr):
            with image_fetcher() as image_file:
                space = self._get_random_space()

                post = space.creator.create_post(
                    is_public=True,
                    title=make_fake_post_title(),
                    text=fake.text(max_nb_chars=300),
                    image=image_file,
                    community_id=space.id,
                )
                self._generate_reactions(post, users)
                comment_count = random.randint(1, 5)
                for _ in range(comment_count):
                    post_comment = post.comment(fake.text(max_nb_chars=300), random.choice(users))
                    if random.random() < 0.2:
                        self._generate_reactions(post_comment, users)

    def generate_insights(self, nr):
        print(f"generate {nr} insights with poll and discussion")
        users = self._get_random_users(int(nr / 1.5))
        if not users:
            raise CommandError(NO_USERS_AVAILABLE)
        posts = Post.objects.filter(is_public=True).all()[: int(nr * 4)]
        if not posts:
            raise CommandError(NO_POSTS_AVAILABLE)
        for _ in range(nr):
            with image_fetcher() as image_file:
                creator = random.choice(users)
                insight = Insight.objects.create(
                    creator=creator,
                    title=make_fake_post_title(),
                    description=fake.text(max_nb_chars=300),
                    date_published=now(),
                    header_image=image_file,
                )
                poll = Poll.create_poll(question_text="How are you feeling?", creator=creator, is_public=True)
                Choice.objects.create(poll_id=poll.id, choice_text="Great")
                insight.polls.set([poll])
                discussion = Discussion.objects.create(insight_id=insight.id, question="What do you think?")
                insight.discussions.set([discussion])

    def generate_spaces(self, nr):
        print(f"generate {nr} spaces with task")
        users = self._get_random_users(int(nr / 1.5))
        if not users:
            raise CommandError(NO_USERS_AVAILABLE)
        topic_slugs = list(get_args(TopicV2))
        if not topic_slugs:
            raise CommandError(NO_TOPICS_AVAILABLE)
        for _ in range(nr):
            with image_fetcher() as image_file:
                creator = random.choice(users)
                community = creator.create_community(
                    title=make_community_title(),
                    type="P",
                    description=fake.text(max_nb_chars=300),
                    avatar=image_file,
                    cover=image_file,
                    topics_v2=[random.choice(topic_slugs)],
                    location="Germany",
                )
                creator.create_task(
                    space_id=community.id,
                    name=fake.text(max_nb_chars=20),
                    description=fake.catch_phrase(),
                    visibility=VisibilityType.PUBLIC,
                    duration=Task.Duration.HOURS_2to4,
                    location_type="REMOTE",
                    contact_email=fake.email(),
                    slots_available=10,
                    regularity="REGULARLY",
                )
