import random

from django.core.management import BaseCommand
from django.utils.timezone import now

from openbook_auth.models import User
from openbook_circles.models import Circle
from openbook_common.tests.helpers import (
    make_users,
    make_fake_post_title,
    make_fake_post_text,
    make_fake_post_comment_text,
)
from openbook_insights.models import Insight
from openbook_posts.models import Post

prefix = "generate_"


class Command(BaseCommand):
    """
    creating a method that starts with the prefix (see above) automatically adds a new generator to this command.
    """

    help = """Generate dummy data. Check help options for the type of objects that can be created, like --user, --post, ..."""

    def add_arguments(self, parser):
        for g in [key[len(prefix) :] for key in dir(Command) if key.startswith(prefix)]:
            parser.add_argument(f"--{g}", nargs=1, type=int)

    def handle(self, *args, **options):
        for key, value in options.items():
            if hasattr(self, prefix + key) and value:
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
        for i in range(nr):
            random.choice(users).create_public_post(title=make_fake_post_title(), text=make_fake_post_text())

    def generate_post_with_comment(self, nr):
        print(f"generate {nr} posts with comments")
        users = self._get_random_users(int(nr / 1.5))
        for i in range(nr):
            post = random.choice(users).create_public_post(title=make_fake_post_title(), text=make_fake_post_text())
            comment_count = random.randint(1, 5)
            for j in range(comment_count):
                post.comment(make_fake_post_comment_text(), random.choice(users))

    def generate_insight(self, nr):
        print(f"generate {nr} insights")
        users = self._get_random_users(int(nr / 1.5))
        posts = Post.objects.filter(circles__id=Circle.get_world_circle_id()).all()[: int(nr * 4)]
        for i in range(nr):
            insight = Insight.objects.create(
                creator=random.choice(users),
                title=make_fake_post_title(),
                date_published=now(),
            )
            for j in range(random.randint(1, 5)):
                insight.posts.add(random.choice(posts))
