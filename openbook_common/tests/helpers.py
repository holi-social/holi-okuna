import random
import tempfile
import uuid
from typing import List, Optional

from PIL import Image
from asgiref.sync import async_to_sync
from django.conf import settings
from django.contrib.contenttypes.models import ContentType
from django.core.files.uploadedfile import SimpleUploadedFile
from django.utils import timezone
from faker import Faker
from mixer.backend.django import mixer

from comments.models import Comment
from feed_posts.models import FeedPost
from openbook.graphql_schema import schema
from openbook_auth.models import EngagementLevelChoice, User, UserProfile
from openbook_categories.models import Category
from openbook_circles.models import Circle
from openbook_common.enums import VisibilityType
from openbook_common.models import (
    Badge,
    Emoji,
    EmojiGroup,
    Language,
    ProxyBlacklistedDomain,
)
from openbook_common.utils.helpers import get_random_pastel_color
from openbook_communities.models import CollaborationTool, Community, ExternalLink, SpacesRelationship, Task
from openbook_devices.models import Device
from openbook_hashtags.models import Hashtag
from openbook_insights.models import Discussion
from openbook_insights.models.insight import Insight
from openbook_lists.models import List as ListModel
from openbook_moderation.models import (
    ModeratedObject,
    ModeratedObjectLog,
    ModerationCategory,
    ModerationPenalty,
    ModerationReport,
)
from openbook_notifications.models import Notification
from openbook_posts.models import Post
from openbook_terms.models import SDG, Skill, Topic, FeedPostCategory

fake = Faker()

simple_jpeg_bytes = b"\xff\xd8\xff\xe0\x00\x10JFIF\x00\x01\x01\x01\x00H\x00H\x00\x00\xff\xdb\x00C\x00\x03\x02\x02\x02\x02\x02\x03\x02\x02\x02\x03\x03\x03\x03\x04\x06\x04\x04\x04\x04\x04\x08\x06\x06\x05\x06\t\x08\n\n\t\x08\t\t\n\x0c\x0f\x0c\n\x0b\x0e\x0b\t\t\r\x11\r\x0e\x0f\x10\x10\x11\x10\n\x0c\x12\x13\x12\x10\x13\x0f\x10\x10\x10\xff\xc9\x00\x0b\x08\x00\x01\x00\x01\x01\x01\x11\x00\xff\xcc\x00\x06\x00\x10\x10\x05\xff\xda\x00\x08\x01\x01\x00\x00?\x00\xd2\xcf \xff\xd9"


def make_authentication_headers_for_user(user):
    return {
        "X-Holi-User-ID": f"{user.username}",
        "X-Holi-User-Email": f"{user.email}",
    }


def make_fake_post_title():
    return fake.text(max_nb_chars=settings.POST_TITLE_MAX_LENGTH)


def make_fake_post_text():
    return fake.text(max_nb_chars=settings.POST_MAX_LENGTH)


def make_fake_question_text():
    return fake.text(max_nb_chars=200)


def make_fake_post_comment_text():
    return fake.text(max_nb_chars=settings.POST_COMMENT_MAX_LENGTH)


def make_user(
    username: Optional[str] = None,  # UUID
    invite_count: Optional[int] = None,
    name: Optional[str] = None,
    last_name: Optional[str] = None,
    visibility=User.VISIBILITY_TYPE_OKUNA,
    date_joined=None,
    identity=None,
    email=None,
    tracking_consent_analytics=False,
    tracking_consent_personalization=False,
) -> User:
    defined_arguments = {k: v for k, v in locals().items() if v is not None}
    defined_arguments.setdefault("username", str(uuid.uuid4()))
    defined_arguments["id"] = defined_arguments["username"]

    user = mixer.blend(User, **defined_arguments)
    profile = make_profile(user, **defined_arguments)
    if user.profile.full_name() and not user.identity:
        user.identity = User.sanitize_identity_input(user.profile.full_name())
        user.save()

    return user


def make_global_moderator() -> User:
    moderator = make_user()
    moderator.is_moderator = True
    return moderator


def make_badge():
    return mixer.blend(Badge)


def make_users(amount):
    users = mixer.cycle(amount).blend(User, username=uuid.uuid4)
    for user in users:
        make_profile(user=user)
    return users


def make_profile(
    user: Optional[User] = None,
    name: Optional[str] = None,
    last_name: Optional[str] = None,
    **kwargs,
) -> UserProfile:
    defined_arguments = {k: v for k, v in locals().items() if v is not None}
    return mixer.blend(UserProfile, **defined_arguments)


def make_emoji(group=None):
    return mixer.blend(Emoji, group=group)


def make_hashtag(name=None):
    hashtag_name = name if name else make_hashtag_name()
    return mixer.blend(Hashtag, name=hashtag_name, color=get_random_pastel_color())


def make_hashtag_name():
    return fake.unique.word().lower()


def make_emoji_group(is_reaction_group=False):
    return mixer.blend(EmojiGroup, is_reaction_group=is_reaction_group)


def make_reactions_emoji_group():
    return mixer.blend(EmojiGroup, is_reaction_group=True)


def make_circle(creator):
    return mixer.blend(Circle, creator=creator)


def make_user_name():
    return fake.name()


def make_user_last_name():
    return fake.name()


def make_user_about_me():
    return fake.text(max_nb_chars=settings.PROFILE_ABOUT_ME_MAX_LENGTH)


def make_user_location():
    return fake.text(max_nb_chars=settings.PROFILE_LOCATION_MAX_LENGTH)


def make_user_pronouns():
    return fake.text(max_nb_chars=settings.PROFILE_PRONOUNS_MAX_LENGTH)


def make_user_engagement_level():
    engagement_level_list = list(EngagementLevelChoice)
    return random.choice(engagement_level_list)  # noqa: S311


def make_user_avatar():
    image = Image.new("RGB", (100, 100))
    tmp_file = tempfile.NamedTemporaryFile(suffix=".jpg")
    image.save(tmp_file)
    tmp_file.seek(0)
    return tmp_file


def make_user_cover():
    image = Image.new("RGB", (100, 100))
    tmp_file = tempfile.NamedTemporaryFile(suffix=".jpg")
    image.save(tmp_file)
    tmp_file.seek(0)
    return tmp_file


def make_post_image():
    image = Image.new("RGB", (100, 100))
    tmp_file = tempfile.NamedTemporaryFile(suffix=".jpg")
    image.save(tmp_file)
    tmp_file.seek(0)
    return tmp_file


def make_post(user: Optional[User] = None, title: Optional[str] = None, text: Optional[str] = None) -> Post:
    return (user or make_user()).create_post(
        is_public=True, text=text or make_fake_post_text(), title=title or make_fake_post_title()
    )


def make_community_post() -> Post:
    creator = make_user()
    user = make_user()
    community = make_community(creator=creator)
    community.add_member(user)

    return user.create_community_post(
        space_id=community.id,
        community_name=community.id,
        text=make_fake_post_text(),
        title=make_fake_post_title(),
    )


def make_fake_list_name():
    return fake.text(max_nb_chars=settings.LIST_MAX_LENGTH)


def make_fake_circle_name():
    return fake.text(max_nb_chars=settings.CIRCLE_MAX_LENGTH)


def make_community_avatar():
    community_avatar = Image.new("RGB", (100, 100))
    tmp_file = tempfile.NamedTemporaryFile(suffix=".jpg")
    community_avatar.save(tmp_file)
    tmp_file.seek(0)
    return tmp_file


def make_community_cover():
    community_cover = Image.new("RGB", (100, 100))
    tmp_file = tempfile.NamedTemporaryFile(suffix=".jpg")
    community_cover.save(tmp_file)
    tmp_file.seek(0)
    return tmp_file


def make_community_description():
    return fake.text(max_nb_chars=settings.COMMUNITY_DESCRIPTION_MAX_LENGTH)


def make_community_rules():
    return fake.text(max_nb_chars=settings.COMMUNITY_RULES_MAX_LENGTH)


def make_community_user_adjective():
    return fake.word().title()


def make_community_users_adjective():
    return fake.word().title()


def make_community_name():
    return fake.user_name().lower()


def make_community_title():
    return fake.user_name()


def make_category():
    return mixer.blend(Category)


def make_topic(is_discover_spaces_default=False):
    return mixer.blend(Topic, is_discover_spaces_default=is_discover_spaces_default)


def make_sdg():
    return mixer.blend(SDG)


def make_community_topics():
    community_topics = []

    for _ in range(0, settings.COMMUNITY_TOPICS_MAX_AMOUNT):
        topic = make_topic()
        community_topics.append(topic.id)

    return community_topics


def make_skill():
    return mixer.blend(Skill)


def make_community_invites_enabled():
    return fake.boolean()


def make_community_task(community, skills=None, visibility=VisibilityType.MEMBERS, is_deleted=False) -> Task:
    if not skills:
        skills = [make_skill()]

    deleted_at = timezone.now() if is_deleted else None

    return mixer.blend(Task, community=community, skills=skills, visibility=visibility, deleted_at=deleted_at)


def make_community(
    creator=None,
    type=Community.COMMUNITY_TYPE_PUBLIC,
    title=None,
    topics=None,
    location=None,
    geolocation=None,
    admins: List[User] = None,
    moderators: List[User] = None,
    relationships: list[SpacesRelationship] = None,
    is_deleted: bool = False,
) -> Community:
    if not creator:
        creator = make_user()

    if not title:
        title = make_community_title()

    if not topics:
        topics = make_community_topics()

    if not location:
        location = fake.text(max_nb_chars=settings.COMMUNITY_LOCATION_MAX_LENGTH)

    community = creator.create_community(
        title=title,
        type=type,
        color=fake.hex_color(),
        description=make_community_description(),
        rules=make_community_rules(),
        user_adjective=make_community_user_adjective(),
        users_adjective=make_community_users_adjective(),
        categories_names=[make_category().name],
        invites_enabled=make_community_invites_enabled(),
        location=location,
    )
    community.topics.set(topics)
    community.geolocation = geolocation
    if admins:
        for admin in admins:
            community.add_member(admin)
            community.add_administrator(admin)
    if moderators:
        for moderator in moderators:
            community.add_member(moderator)
            community.add_moderator(moderator)

    if relationships:
        community.network_relationships.set(relationships)

    community.is_deleted = is_deleted
    community.save()

    return community


def make_private_community(creator):
    return make_community(creator=creator, type=Community.COMMUNITY_TYPE_PRIVATE)


def make_notification(owner, notification_type=None):
    content_type = ContentType.objects.filter(app_label__startswith="openbook_")[0]
    if notification_type:
        return mixer.blend(
            Notification,
            owner=owner,
            notification_type=notification_type,
            content_type=content_type,
            object_id=uuid.uuid4(),
        )
    else:
        return mixer.blend(Notification, owner=owner, content_type=content_type, object_id=uuid.uuid4())


def make_device(owner):
    return mixer.blend(Device, owner=owner)


def make_moderation_category(severity=ModerationCategory.SEVERITY_MEDIUM):
    return mixer.blend(ModerationCategory, severity=severity)


def make_moderation_report_description():
    return fake.text(max_nb_chars=settings.MODERATION_REPORT_DESCRIPTION_MAX_LENGTH)


def make_moderated_object_description():
    return fake.text(max_nb_chars=settings.MODERATED_OBJECT_DESCRIPTION_MAX_LENGTH)


def make_list(creator):
    return mixer.blend(ListModel, creator=creator)


def make_moderated_object(
    community=None,
):
    return mixer.blend(ModeratedObject, community=community)


def make_moderated_object_log(moderated_object=None):
    return mixer.blend(ModeratedObjectLog, moderated_object=moderated_object)


def make_moderated_object_report(moderated_object=None):
    return mixer.blend(ModerationReport, moderated_object=moderated_object)


def make_moderation_penalty(user):
    return mixer.blend(ModerationPenalty, user=user)


def make_random_language():
    return mixer.blend(Language)


def make_proxy_blacklisted_domain(domain):
    return mixer.blend(ProxyBlacklistedDomain, domain=domain)


def get_test_usernames():
    return ["j_oel", "j.o.e.l", "j03l", "j"]


def get_test_valid_hashtags():
    return [
        "1337test",
        "hello",
        "thisisasomewhatmoderateword",
        "thisisatest123",
        "hello_123",
        "_heythere",
        "osmaodmoasmdoasodasdasdasdsassaa",
    ]


def get_test_invalid_hashtags():
    return [
        "1337",
        "",
        "!@#!@a",
        ".",
    ]


def get_test_videos():
    return [
        {
            "path": "openbook_common/tests/files/test_video.mp4",
            "duration": 5.312,
            "width": 1280,
            "height": 720,
        },
        {
            "path": "openbook_common/tests/files/test_video.3gp",
            "duration": 40.667,
            "width": 176,
            "height": 144,
        },
        {
            "path": "openbook_common/tests/files/test_gif_medium.gif",
            "duration": 1.5,
            "width": 312,
            "height": 312,
        },
        {
            "path": "openbook_common/tests/files/test_gif_tiny.gif",
            "duration": 0.771,
            "width": 256,
            "height": 256,
        },
    ]


def get_test_images():
    return [
        {
            "path": "openbook_common/tests/files/test_image_tiny.png",
            "width": 272,
            "height": 170,
        },
        {
            "path": "openbook_common/tests/files/test_image_small.png",
            "width": 912,
            "height": 513,
        },
        {
            "path": "openbook_common/tests/files/test_image_medium.png",
            "width": 5891,
            "height": 2271,
        },
        {
            "path": "openbook_common/tests/files/test_image_tiny.jpg",
            "width": 300,
            "height": 300,
        },
        {
            "path": "openbook_common/tests/files/test_image_small.jpg",
            "width": 2192,
            "height": 2921,
        },
        {
            "path": "openbook_common/tests/files/test_image_medium.jpg",
            "width": 10751,
            "height": 4287,
        },
    ]


def get_test_image():
    return get_test_images()[0]


def get_test_video():
    return get_test_videos()[0]


def make_collaboration_tool(
    creator=None,
    community=None,
    url=None,
    title=None,
    description=None,
    collection_type=None,
) -> Community:
    if not creator:
        creator = make_user()

    if not community:
        community = make_community()

    if not url:
        url = fake.url()

    if not title:
        title = fake.text(max_nb_chars=settings.COLLABORATION_TOOL_TITLE_MAX_LENGTH)

    if not description:
        description = fake.text(max_nb_chars=settings.COLLABORATION_TOOL_TITLE_MAX_LENGTH)

    if not collection_type:
        collection_type = fake.random_element(elements=["COLLABORATION", "COMMUNICATION"])

    return mixer.blend(
        CollaborationTool,
        creator=creator,
        community=community,
        url=url,
        title=title,
        description=description,
        collection_type=collection_type,
    )


def make_external_link(
    community=None,
    url=None,
    type=None,
    name=None,
) -> Community:
    if not community:
        community = make_community()

    if not url:
        url = fake.url()

    if not type:
        type = fake.random_element(elements=["instagram", "facebook"])

    if not name:
        name = fake.text(max_nb_chars=settings.EXTERNAL_LINK_NAME_MAX_LENGTH)

    return mixer.blend(
        ExternalLink,
        community=community,
        url=url,
        type=type,
        name=name,
    )


def assert_paged_results_equal(results: dict, expected_data: List[dict[str, any]]):
    assert results["totalResults"] == len(expected_data)

    for el in expected_data:
        assert el in results["data"]


def assert_is_unauthorized(response):
    assert response.data is None
    assert "Unauthorized" in str(response.errors[0].message)
    assert "UNAUTHORIZED" == str(response.errors[0].extensions["code"])


def assert_is_forbidden(response):
    assert "Forbidden" in str(response.errors[0].message)
    assert "FORBIDDEN" == str(response.errors[0].extensions["code"])


def assert_is_404(response):
    assert "Object not found" in str(response.errors[0].message)
    assert "NOT_FOUND" == str(response.errors[0].extensions["code"])


def create_large_image_file():
    test_image = get_test_images()[-1]

    with open(test_image["path"], "rb") as file:
        content = file.read()
        return SimpleUploadedFile(name="image.jpg", content=content)


def create_video_file():
    test_video = get_test_videos()[0]

    with open(test_video["path"], "rb") as file:
        content = file.read()
        return SimpleUploadedFile(name="video.mp4", content=content)


def check_app_version(version: str, build_number: str):
    response = async_to_sync(schema.execute)(
        f"""
        query {{
            checkAppVersion(version: "{version}", buildNumber: "{build_number}") {{
                needUpdate
                appStoreUrl
                playStoreUrl
            }}
        }}
        """,
    )
    return response


def make_space_post_comment():
    space = make_community()
    post_author = make_user()
    post = mixer.blend(Post, creator=post_author, community=space, is_public=True, status=Post.STATUS_PUBLISHED)
    commenter = make_user()
    text = fake.paragraph()

    post_comment = mixer.blend(Comment, commenter=commenter, commentable=post, text=text)

    return post_comment


def make_space_post_comment_with_mention():
    space = make_community()
    post_author = make_user()
    post = mixer.blend(Post, creator=post_author, community=space, is_public=True, status=Post.STATUS_PUBLISHED)
    commenter = make_user()
    mentioned_user = make_user()
    text = fake.paragraph()

    post_comment = mixer.blend(
        Comment, commenter=commenter, commentable=post, text=f"@{mentioned_user.username} {text}"
    )

    return post_comment


def make_feed_post_comment_with_mention():
    post_author = make_user()
    feed_post = mixer.blend(FeedPost, creator=post_author)
    commenter = make_user()
    mentioned_user = make_user()
    text = fake.paragraph()

    post_comment = mixer.blend(
        Comment, commenter=commenter, commentable=feed_post, text=f"@{mentioned_user.username} {text}"
    )

    return post_comment


def make_insight_discussion_comment_with_mention():
    insight = make_insight()
    discussion = mixer.blend(Discussion, insight=insight, question="Question")
    commenter = make_user()
    mentioned_user = make_user()
    text = fake.paragraph()

    post_comment = mixer.blend(
        Comment, commenter=commenter, commentable=discussion, text=f"@{mentioned_user.username} {text}"
    )

    return post_comment


def make_insight():
    author = make_user()
    insight = mixer.blend(Insight, creator=author, date_published=timezone.now())
    return insight


def make_feed_post_category():
    return mixer.blend(FeedPostCategory)


def make_feed_post_founder_update_category():
    return mixer.blend(FeedPostCategory, slug="founder-update")
