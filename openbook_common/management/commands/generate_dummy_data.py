import random
import io
import sys
from contextlib import contextmanager
from urllib import request

from django.core.files.uploadedfile import InMemoryUploadedFile
from django.core.management import BaseCommand, CommandError
from django.utils.timezone import now
from faker import Faker

from openbook import settings
from openbook_auth.models import User
from openbook_circles.models import Circle
from openbook_common.tests.helpers import (
    make_users,
    make_fake_post_title,
    make_community_title,
)
from openbook_insights.models import Insight
from openbook_posts.models import Post
from openbook_terms.models import Topic

fake = Faker()
prefix = "generate_"


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
                print(f'{key}: {value}')
                fn = getattr(self, prefix + key)
                fn(value[0])

    def _get_random_users(self, nr_of_users):
        return User.objects.filter(profile__isnull=False).all()[: max(10, nr_of_users)]

    def generate_user(self, nr):
        print(f"generate {nr} users")
        make_users(nr)

    def generate_post(self, nr):
        print(f"generate {nr} posts")
        users = self._get_random_users(int(nr / 1.5))
        if not users:
            raise CommandError("no users available, please generate users first")
        for i in range(nr):
            with image_fetcher() as image_file:
                random.choice(users).create_public_post(
                    title=make_fake_post_title(),
                    text=fake.text(max_nb_chars=300),
                    image=image_file,
                )

    def generate_post_with_comment(self, nr):
        print(f"generate {nr} posts with comments")
        users = self._get_random_users(int(nr / 1.5))
        if not users:
            raise CommandError("no users available, please generate users first")
        for i in range(nr):
            with image_fetcher() as image_file:
                post = random.choice(users).create_public_post(
                    title=make_fake_post_title(), text=fake.text(max_nb_chars=300), image=image_file
                )
                comment_count = random.randint(1, 5)
                for j in range(comment_count):
                    post.comment(fake.text(max_nb_chars=300), random.choice(users))

    def generate_insight(self, nr):
        print(f"generate {nr} insights")
        users = self._get_random_users(int(nr / 1.5))
        if not users:
            raise CommandError("no users available, please generate users first")
        posts = Post.objects.filter(circles__id=Circle.get_world_circle_id()).all()[: int(nr * 4)]
        if not posts:
            raise CommandError("no posts available, please generate posts first")
        for i in range(nr):
            with image_fetcher() as image_file:
                insight = Insight.objects.create(
                    creator=random.choice(users),
                    title=make_fake_post_title(),
                    description=fake.text(max_nb_chars=300),
                    date_published=now(),
                    header_image=image_file,
                )
                for j in range(random.randint(1, 8)):
                    insight.posts.add(random.choice(posts))

    def generate_space(self, nr):
        print(f"generate {nr} spaces")
        users = self._get_random_users(int(nr / 1.5))
        if not users:
            raise CommandError("no users available, please generate users first")
        topic_ids = [t.id for t in Topic.objects.all()]
        if not topic_ids:
            raise CommandError("no topics available, please generate topics first (via loaddata)")
        for i in range(nr):
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
