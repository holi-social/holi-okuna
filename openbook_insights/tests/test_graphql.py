import logging

import pytest
from asgiref.sync import async_to_sync
from benedict import benedict
from django.contrib.auth.models import AnonymousUser
from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.management import call_command
from django.test import AsyncClient
from django.utils import timezone

from openbook.graphql_schema import schema
from openbook_common.tests.helpers import (
    make_fake_post_text,
    make_fake_post_title,
    make_insight,
    make_user,
    simple_jpeg_bytes,
)
from openbook_insights.models import Insight
from openbook_insights.tests.helpers import get_insight

logger = logging.getLogger(__name__)


@pytest.fixture(scope="session")
def client():
    return AsyncClient()


@pytest.fixture(scope="session")
def django_db_setup(django_db_setup, django_db_blocker):
    with django_db_blocker.unblock():
        call_command("loaddata", "openbook_moderation/fixtures/moderation_categories.json")


@pytest.mark.django_db
class TestInsights:
    def test_insights_by_user_id_success_user_anonymous(self):
        insight_user = make_user()
        insight_user_2 = make_user()

        now = timezone.now()
        insight1 = Insight.objects.create(
            creator=insight_user,
            title="Insight  Foo",
            header_image=SimpleUploadedFile(name="cover.jpg", content=simple_jpeg_bytes),
            date_published=now,
        )
        insight2 = Insight.objects.create(
            creator=insight_user, title="Insight 2", date_published=now - timezone.timedelta(days=1)
        )
        insight3 = Insight.objects.create(creator=insight_user_2, title="Insight 3", date_published=now)

        response = async_to_sync(schema.execute)(
            f"""
            query {{
                insightsByUserId(id: "{insight_user.username}") {{
                    data {{
                        id
                        title
                        headerImage
                    }}
                    totalResults
                }}
            }}
            """,
            context_value=benedict({"request": {"user": AnonymousUser}}),
        )

        assert response.errors is None
        insights = response.data["insightsByUserId"]["data"]
        assert len(insights) == 2

        insight1_result = insights[0]
        assert insight1_result["title"] == insight1.title
        assert insight1_result["headerImage"] == insight1.header_image

        insight2_result = insights[1]
        assert insight2_result["title"] == insight2.title

        assert insight3.title not in [insight["title"] for insight in insights]

    def test_insights_by_user_id_success_user_authenticated(self):
        insight_user = make_user()
        insight_user_2 = make_user()

        now = timezone.now()
        insight1 = Insight.objects.create(
            creator=insight_user,
            title="Insight  Foo",
            header_image=SimpleUploadedFile(name="cover.jpg", content=simple_jpeg_bytes),
            date_published=now,
        )
        insight2 = Insight.objects.create(
            creator=insight_user, title="Insight 2", date_published=now - timezone.timedelta(days=1)
        )
        insight3 = Insight.objects.create(creator=insight_user_2, title="Insight 3", date_published=now)

        response = async_to_sync(schema.execute)(
            f"""
            query {{
                insightsByUserId(id: "{insight_user.username}") {{
                    data {{
                        id
                        title
                        headerImage
                        headerImageBlurhash
                    }}
                    totalResults
                }}
            }}
            """,
            context_value=benedict({"request": {"user": insight_user_2}}),
        )

        assert response.errors is None
        insights = response.data["insightsByUserId"]["data"]
        assert len(insights) == 2

        insight1_result = insights[0]
        assert insight1_result["title"] == insight1.title
        assert insight1_result["headerImage"] == insight1.header_image
        assert insight1_result["headerImageBlurhash"] is not None

        insight2_result = insights[1]
        assert insight2_result["title"] == insight2.title

        assert insight3.title not in [insight["title"] for insight in insights]

    def test_insights_by_user_id_error_blocked_user(self):
        insight_user = make_user()
        insight_user_2 = make_user()

        insight_user_2.block_user_with_id(insight_user.id)

        now = timezone.now()
        Insight.objects.create(
            creator=insight_user,
            title="Insight  Foo",
            header_image=SimpleUploadedFile(name="cover.jpg", content=simple_jpeg_bytes),
            date_published=now,
        )
        Insight.objects.create(
            creator=insight_user, title="Insight 2", date_published=now - timezone.timedelta(days=1)
        )
        Insight.objects.create(creator=insight_user_2, title="Insight 3", date_published=now)

        response = async_to_sync(schema.execute)(
            f"""
            query {{
                insightsByUserId(id: "{insight_user.username}") {{
                    data {{
                        id
                        title
                        headerImage
                    }}
                    totalResults
                }}
            }}
            """,
            context_value=benedict({"request": {"user": insight_user_2}}),
        )

        assert response.data is None
        assert len(response.errors) == 1
        assert "Object not found" == str(response.errors[0].message)

    def test_select_last_insights(self):
        insight_user = make_user()
        posting_user = make_user()
        other_user = make_user()
        private_user = make_user()

        post_text_public = make_fake_post_text()
        post_title_public = make_fake_post_title()
        post_text_draft = make_fake_post_text()
        post_title_draft = make_fake_post_title()

        now = timezone.now()
        insight1 = Insight.objects.create(
            creator=insight_user,
            title="Insight 1",
            date_published=now,
        )

        post1 = posting_user.create_post(text=post_text_public, title=post_title_public, is_public=True)
        post2 = posting_user.create_post(text=post_text_public, title=post_title_public, is_public=True)
        post3 = posting_user.create_post(text=post_text_draft, title=post_title_draft, is_draft=True, is_public=True)
        post_private = private_user.create_post(
            circles_ids=[private_user.connections_circle_id],
            text="private post",
            title="private post",
            is_public=False,
        )
        insight1.posts.add(post1, post2, post3, post_private)

        insight2 = Insight.objects.create(
            id="ffffffff-ffff-ffff-ffff-ffffffffffff",
            creator=posting_user,
            title="Insight 2",
            date_published=now - timezone.timedelta(days=1),
        )
        post4 = posting_user.create_post(text=post_text_public, title=post_title_public, is_public=True)
        post4.comment(text=post_text_public, commenter=other_user)
        insight2.posts.add(post4)

        insight3 = Insight.objects.create(
            id="00000000-0000-0000-0000-000000000001",
            creator=posting_user,
            title="Insight 3",
            date_published=now - timezone.timedelta(days=1),
        )
        post5 = posting_user.create_post(text=post_text_public, title=post_title_public, is_public=True)
        insight3.posts.add(post5)

        insight4 = Insight.objects.create(
            id="00000000-0000-0000-0000-000000000000",
            creator=posting_user,
            title="Insight 4",
            date_published=now - timezone.timedelta(days=2),
        )

        response = async_to_sync(schema.execute)(
            """
            query {
                lastInsights {
                    data {
                        title
                        numberOfPosts
                        posts {
                            title
                        }
                        involvedUsers {
                            totalResults
                            data {
                              fullName
                            }
                        }
                    }
                }
            }
            """,
            context_value=benedict({"request": {"user": AnonymousUser}}),
        )

        insights = response.data["lastInsights"]["data"]
        assert len(insights) == 4
        # insight1 = next(i for i in insights if i["title"] == insight1_title)
        # insight2 = next(i for i in insights if i["title"] == insight2_title)
        insight1_result = insights[0]
        assert insight1_result["title"] == insight1.title
        assert insight1_result["numberOfPosts"] == 2
        assert insight1_result["posts"][0]["title"] == post_title_public
        assert insight1_result["posts"][1]["title"] == post_title_public
        assert insight1_result["involvedUsers"]["totalResults"] == 2

        insight2_result = insights[1]
        assert insight2_result["title"] == insight3.title
        assert insight2_result["numberOfPosts"] == 1
        assert insight2_result["involvedUsers"]["totalResults"] == 1

        insight3_result = insights[2]
        assert insight3_result["title"] == insight2.title
        assert insight3_result["numberOfPosts"] == 1
        assert insight3_result["involvedUsers"]["totalResults"] == 2

        insight4_result = insights[3]
        assert insight4_result["title"] == insight4.title
        assert insight4_result["numberOfPosts"] == 0
        assert insight4_result["involvedUsers"]["totalResults"] == 1

    def test_last_insights_with_blocked_user(self):
        insight_user = make_user(name="InsightUser")
        query_user = make_user(name="QueryUser")
        blocked_user = make_user(name="Blocked")
        query_user.block_user_with_id(blocked_user.id)

        now = timezone.now()
        post1 = insight_user.create_post(title="not blocked post", text=(make_fake_post_text()), is_public=True)
        post2 = blocked_user.create_post(title="blocked post", text=(make_fake_post_text()), is_public=True)
        insight1 = Insight.objects.create(
            creator=insight_user,
            title="Insight  Foo",
            date_published=now,
        )
        insight1.posts.add(post1, post2)

        Insight.objects.create(
            creator=blocked_user, title="Insight 2 Blocked", date_published=now - timezone.timedelta(days=1)
        )

        response = async_to_sync(schema.execute)(
            """
            query {
                lastInsights {
                    data {
                        title
                        numberOfPosts
                        posts {
                            title
                            creator {
                                fullName
                            }
                        }
                        involvedUsers {
                            totalResults
                            data {
                              fullName
                            }
                        }
                    }
                }
            }
            """,
            context_value=benedict({"request": {"user": query_user}}),
        )
        insights = response.data["lastInsights"]["data"]
        assert len(insights) == 1
        insight1_result = insights[0]
        assert insight1_result["title"] == insight1.title
        assert len(insight1_result["posts"]) == 1


@pytest.mark.django_db
class TestDiscussions:
    def test_should_list_discussions(self):
        user = make_user(name="InsightUser")
        insight = make_insight()
        insight.discussions.create(question="What do you think?")

        response = get_insight(user, insight.id)

        assert response.errors is None
        insight_data = response.data["insightById"]
        assert insight_data["id"] == str(insight.id)
        assert len(insight_data["discussions"]) == 1
        assert insight_data["discussions"][0]["question"] == "What do you think?"
