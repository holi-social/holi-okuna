from django.core.management.base import BaseCommand
from langdetect.lang_detect_exception import LangDetectException

from openbook_common.helpers import get_language_for_text
from openbook_common.utils.model_loaders import get_comment_model, get_post_model


class Command(BaseCommand):
    help = "Assigns Language to Post and Comment models, usage python manage.py assign_language --type posts|comments"

    def add_arguments(self, parser):
        parser.add_argument(
            "--type",
            type=str,
            help="Type of model to assign lang to, valid values: posts, comments",
        )

    def handle(self, *args, **options):
        if options["type"] == "posts":
            self.assign_language_posts()

        if options["type"] == "comments":
            self.assign_language_comments()

    def assign_language_posts(self):
        Post = get_post_model()
        posts = Post.objects.filter(text__isnull=False)
        for post in posts:
            try:
                language = get_language_for_text(post.text)
            except LangDetectException:
                print("Caught exception while detecting language, skipping")

            if language:
                post.language = language
                post.save()
            else:
                print("Could not detect language for id", post.id)

    def assign_language_comments(self):
        Comment = get_comment_model()
        post_comments = Comment.objects.filter(text__isnull=False)
        for post_comment in post_comments:
            try:
                language = get_language_for_text(post_comment.text)
            except LangDetectException:
                print("Caught exception while detecting language, skipping")

            if language:
                post_comment.language = language
                post_comment.save()
            else:
                print("Could not detect language for id", post_comment.id)
