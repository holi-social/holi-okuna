import io
import random
import sys
from contextlib import contextmanager
from urllib import request

from django.core.files.uploadedfile import InMemoryUploadedFile
from django.core.management import BaseCommand, CommandError
from django.utils.timezone import now
from faker import Faker

from openbook import settings
from openbook.helpers import publish_user_name_updated_event
from openbook_auth.models import User
from openbook_auth.tasks import generate_identity_when_needed
from openbook_common.tests.helpers import (
    make_community_title,
    make_fake_post_title,
    make_users,
)
from openbook_common.enums import ReactionType
from openbook_insights.models import Insight
from openbook_posts.models import Post
from openbook_terms.models import Topic

fake = Faker()
prefix = "generate_"

NO_USERS_AVAILABLE = "no users available, please generate users first"
NO_POSTS_AVAILABLE = "no posts available, please generate posts first"
NO_TOPICS_AVAILABLE = "no topics available, please generate topics first (via loaddata)"


@contextmanager
def image_fetcher(url=f"{settings.IMAGEKIT_URL}/tr:w-300,h-300/default-image.jpg"):
    with request.urlopen(url) as response:
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
        return User.objects.filter(profile__isnull=False).all()[: max(10, nr_of_users)]

    @staticmethod
    def generate_user(nr):
        print(f"generate {nr} users")
        users = make_users(nr)
        for user in users:
            generate_identity_when_needed(user)
            publish_user_name_updated_event(user=user)

    def generate_post(self, nr):
        print(f"generate {nr} posts")
        users = self._get_random_users(int(nr / 1.5))
        if not users:
            raise CommandError(NO_USERS_AVAILABLE)
        for _ in range(nr):
            with image_fetcher() as image_file:
                random.choice(users).create_post(
                    is_public=True,
                    title=make_fake_post_title(),
                    text=fake.text(max_nb_chars=300),
                    image=image_file,
                )

    def generate_post_with_comment(self, nr):
        print(f"generate {nr} posts with comments")
        users = self._get_random_users(int(nr / 1.5))
        if not users:
            raise CommandError(NO_USERS_AVAILABLE)
        for _ in range(nr):
            with image_fetcher() as image_file:
                post = random.choice(users).create_post(
                    is_public=True, title=make_fake_post_title(), text=fake.text(max_nb_chars=300), image=image_file
                )
                comment_count = random.randint(1, 5)
                for _ in range(comment_count):
                    post.comment(fake.text(max_nb_chars=300), random.choice(users))

    @staticmethod
    def _generate_reactions(obj, users):
        for user in users:
            if random.choice([False, True]):
                obj.react(user, random.choice([_ for _ in ReactionType]))

    def generate_post_with_comment_and_reaction(self, nr):
        print(f"generate {nr} posts with comments and reactions")
        users = self._get_random_users(int(nr / 1.5))
        if not users:
            raise CommandError(NO_USERS_AVAILABLE)
        for _ in range(nr):
            with image_fetcher() as image_file:
                post = random.choice(users).create_post(
                    is_public=True, title=make_fake_post_title(), text=fake.text(max_nb_chars=300), image=image_file
                )
                self._generate_reactions(post, users)
                comment_count = random.randint(1, 5)
                for _ in range(comment_count):
                    post_comment = post.comment(fake.text(max_nb_chars=300), random.choice(users))
                    if random.random() < 0.2:
                        self._generate_reactions(post_comment, users)

    def generate_insight(self, nr):
        print(f"generate {nr} insights")
        users = self._get_random_users(int(nr / 1.5))
        if not users:
            raise CommandError(NO_USERS_AVAILABLE)
        posts = Post.objects.filter(is_public=True).all()[: int(nr * 4)]
        if not posts:
            raise CommandError(NO_POSTS_AVAILABLE)
        for _ in range(nr):
            with image_fetcher() as image_file:
                insight = Insight.objects.create(
                    creator=random.choice(users),
                    title=make_fake_post_title(),
                    description=fake.text(max_nb_chars=300),
                    date_published=now(),
                    header_image=image_file,
                )
                for _ in range(random.randint(1, 8)):
                    insight.posts.add(random.choice(posts))

    def generate_space(self, nr):
        print(f"generate {nr} spaces")
        users = self._get_random_users(int(nr / 1.5))
        if not users:
            raise CommandError(NO_USERS_AVAILABLE)
        topic_ids = [t.id for t in Topic.objects.all()]
        if not topic_ids:
            raise CommandError(NO_TOPICS_AVAILABLE)
        for _ in range(nr):
            with image_fetcher() as image_file:
                random.choice(users).create_community(
                    title=make_community_title(),
                    type="P",
                    description=fake.text(max_nb_chars=300),
                    avatar=image_file,
                    cover=image_file,
                    topic_ids=[random.choice(topic_ids)],
                    location="Germany",
                )
