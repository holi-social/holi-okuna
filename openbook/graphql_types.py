import random
import uuid
from enum import Enum
from uuid import UUID

import strawberry
from typing import List, TypeVar, Optional

from django.db.models import Q
from strawberry_django_plus import gql
from django.db.models import QuerySet

import logging
from openbook_common.models import LinkPreview as LinkPreviewModel
from openbook_common.types import ReactionType
from openbook_common.utils.model_loaders import get_circle_model
from openbook_communities.models import (
    Community as CommunityModel,
    Task as TaskModel,
    CommunityMembership as CommunityMembershipModel,
    ExternalLink as ExternalLinkModel,
    ExternalLinkType,
    CollaborationTool as CollaborationToolModel,
)
from openbook_notifications.models import Notification as NotificationModel
from openbook_posts.models import (
    Post as PostModel,
    PostComment as PostCommentModel,
    PostImage as PostImageModel,
    PostReaction as PostReactionModel,
    PostCommentReaction as PostCommentReactionModel,
)
from openbook_terms.models import (
    Topic as TopicModel,
    SDG as SDGModel,
    Skill as SkillModel,
)
from openbook_auth.models import User as UserModel, UserConnectionStatus, UserBlock
from openbook_insights.models import Insight as InsightModel

logger = logging.getLogger(__name__)

GenericType = TypeVar("GenericType")


@gql.type
class Paged(List[GenericType]):
    data: List[Optional[GenericType]] = gql.django.field(description="The list of items in this pagination window.")
    total_results: int = gql.django.field(description="Total number of items in the filtered dataset.")

    @staticmethod
    def of(query: QuerySet, offset: int, limit: int):
        return Paged(data=query[offset : offset + limit], total_results=query.count())

    def __init__(self, data=[], total_results=0):
        if data is None:
            data = []
        self.data = data
        self.total_results = max(total_results, len(data))


@gql.enum
class UpdateConnectionAction(Enum):
    CONNECT = "CONNECT"
    DISCONNECT = "DISCONNECT"


@gql.enum
class ContentType(Enum):
    POST = "POST"
    POST_COMMENT = "POST_COMMENT"
    USER = "USER"
    SPACE = "SPACE"


@gql.enum
class ReactionAction(Enum):
    SET = "SET"
    REMOVE = "REMOVE"


@gql.enum
class Visibility(Enum):
    PUBLIC = "public"
    PRIVATE = "private"
    ALL = "all"


@gql.type
class Geolocation:
    longitude: float
    latitude: float

    @staticmethod
    def from_point(point):
        if not point:
            return None

        return Geolocation(longitude=point.x, latitude=point.y)


@gql.type
class Reaction:
    type: ReactionType
    count: int


@gql.enum
class NotificationType(Enum):
    PR = strawberry.enum_value("PR", description="POST_REACTION")
    PC = strawberry.enum_value("PC", description="POST_COMMENT")
    PCR = strawberry.enum_value("PCR", description="POST_COMMENT_REPLY")
    PCRA = strawberry.enum_value("PCRA", description="POST_COMMENT_REACTION")
    CR = strawberry.enum_value("CR", description="CONNECTION_REQUEST")
    CA = strawberry.enum_value("CA", description="CONNECTION_ACCEPTED")
    CC = strawberry.enum_value("CC", description="CONNECTION_CONFIRMED")
    F = strawberry.enum_value("F", description="FOLLOW")
    FR = strawberry.enum_value("FR", description="FOLLOW_REQUEST")
    FRA = strawberry.enum_value("FRA", description="FOLLOW_REQUEST_APPROVED")
    CMR = strawberry.enum_value("CMR", description="COMMUNITY_MEMBERSHIP_REQUEST")
    CMRA = strawberry.enum_value("CMRA", description="COMMUNITY_MEMBERSHIP_APPROVED")
    CI = strawberry.enum_value("CI", description="COMMUNITY_INVITE")
    PUM = strawberry.enum_value("PUM", description="POST_USER_MENTION")
    PCUM = strawberry.enum_value("PCUM", description="POST_COMMENT_USER_MENTION")
    CNP = strawberry.enum_value("CNP", description="COMMUNITY_NEW_POST")
    UNP = strawberry.enum_value("UNP", description="USER_NEW_POST")
    REL = strawberry.enum_value("REL", description="RELEASE_INFO")


@gql.enum
class SpaceUserConnectionType(Enum):
    FOLLOWER = "FOLLOWER"
    MEMBERSHIP_REQUESTOR = "MEMBERSHIP_REQUESTOR"
    MEMBER = "MEMBER"
    CREATOR = "CREATOR"
    ADMINISTRATOR = "ADMINISTRATOR"


@gql.django.type(TopicModel)
class Topic:
    id: gql.auto
    title: gql.auto
    slug: gql.auto
    is_discover_spaces_default: gql.auto


@gql.django.type(SDGModel)
class SDG:
    id: gql.auto
    title: gql.auto
    slug: gql.auto
    number: gql.auto


@gql.django.type(SkillModel)
class Skill:
    id: gql.auto
    title: gql.auto
    slug: gql.auto


@gql.django.type(ExternalLinkModel)
class ExternalLink:
    id: gql.auto
    url: gql.auto
    type: ExternalLinkType


@gql.django.type(PostImageModel)
class PostImage:
    id: UUID
    width: int
    height: int
    url: str = gql.django.field(field_name="image")


@gql.django.type(LinkPreviewModel)
class LinkPreview:
    id: gql.auto
    requested_url: gql.auto
    url: gql.auto
    title: gql.auto
    description: gql.auto
    type: gql.auto
    image: gql.auto
    site_name: gql.auto
    fetched_at: gql.auto

    @gql.django.field
    def origin(self) -> str:
        return self.get_origin()


@gql.django.type(UserModel)
class User:
    id: uuid.UUID = gql.django.field(field_name="username")
    avatar_default_color: str
    avatar_label: str

    @gql.django.field(description="Can be an empty string", select_related=["profile"])
    def full_name(self) -> str:
        return self.profile.full_name

    @gql.django.field(select_related=["profile"])
    def avatar(self) -> Optional[str]:
        return self.profile.avatar

    @gql.django.field(select_related=["profile"])
    def first_name(self) -> Optional[str]:
        return self.profile.name

    @gql.django.field(select_related=["profile"])
    def last_name(self) -> Optional[str]:
        return self.profile.last_name

    @gql.django.field(select_related=["profile"])
    def about_me(self) -> Optional[str]:
        return self.profile.about_me

    @gql.django.field(select_related=["profile"])
    def pronouns(self) -> Optional[str]:
        return self.profile.pronouns

    @gql.django.field(select_related=["profile"])
    def location(self) -> Optional[str]:
        return self.profile.location

    @gql.django.field(select_related=["profile"])
    def geolocation(self) -> Optional[Geolocation]:
        return Geolocation.from_point(self.profile.geolocation)

    @gql.django.field(select_related=["profile"])
    def engagement_level(self) -> Optional[str]:
        return self.profile.engagement_level

    @gql.django.field(select_related=["profile__interests"])
    def interests(self) -> List[Optional[Topic]]:
        return self.profile.interests

    @gql.django.field(select_related=["profile__sdgs"])
    def sdgs(self) -> List[Optional[SDG]]:
        return self.profile.sdgs.order_by("number")

    @gql.django.field(select_related=["profile__skills"])
    def skills(self) -> List[Optional[Skill]]:
        return self.profile.skills

    @gql.django.field
    def connection_status_to_myself(self, info) -> Optional[UserConnectionStatus]:
        if info.context.request.user.is_anonymous:
            return None
        return info.context.request.user.get_connection_status_with_user_id(user_id=self.id)


@gql.django.type(CommunityMembershipModel)
class SpaceMember:
    id: gql.auto
    user: User
    community: "Space"
    is_administrator: gql.auto
    created: gql.auto


CollectionType = CollaborationToolModel.CollectionType


@gql.django.type(CollaborationToolModel)
class CollaborationTool:
    id: gql.auto
    url: gql.auto
    title: gql.auto
    description: gql.auto
    collection_type: CollectionType
    domain: gql.auto


@gql.enum
class Regularity(Enum):
    REGULARLY = "regularly"
    PROJECT_BASED = "project-based"
    ONE_TIME = "one-time"


@gql.django.type(TaskModel)
class Task:
    id: gql.auto
    name: gql.auto
    description: gql.auto
    community: "Space"
    creator: User
    created: gql.auto
    slots_available: gql.auto
    slots_taken: gql.auto
    location: gql.auto
    regularity: Regularity
    skills: List[Skill]


@gql.django.type(InsightModel)
class Insight:
    id: gql.auto
    title: gql.auto
    description: gql.auto
    creator: Optional[User] = gql.django.field(select_related=["creator__profile"])
    date_published: gql.auto
    header_image: Optional[str]
    topic: Optional[Topic]

    @gql.django.field(prefetch_related="posts")
    def posts(self, info) -> List["Post"]:
        current_user = info.context.request.user
        return (
            PostModel.objects.filter(insights=self)
            .filter(PostModel.is_visible_query(current_user))
            .filter(UserBlock.not_blocked_query(current_user, "creator"))
            .order_by("created")
        )

    # this should be removed and be replaced by paged posts
    @gql.django.field
    def number_of_posts(self, info) -> int:
        current_user = info.context.request.user
        return (
            PostModel.objects.filter(insights=self)
            .filter(PostModel.is_visible_query(current_user))
            .filter(UserBlock.not_blocked_query(current_user, "creator"))
            .count()
        )

    @gql.django.field(
        description="A list of all users involved. Curator of the insight, Authors of all the posts and all commenters of those posts"
    )
    def involved_users(self, info, offset: int = 0, limit: int = 10) -> Paged[User]:
        current_user = info.context.request.user
        return Paged.of(
            UserModel.objects.select_related("profile")
            .filter(UserModel.is_visible_query(current_user))
            .filter(
                Q(curated_insights=self)
                | (Q(posts__insights=self) & PostModel.is_visible_query(current_user, "posts"))
                | (
                    Q(posts_comments__post__insights=self)
                    & PostCommentModel.is_visible_query(current_user, "posts_comments")
                )
            )
            .distinct(),
            offset,
            limit,
        )


@gql.type
class ReactionCounts:
    HEART: int = 0


@gql.django.type(PostModel)
class Post:
    id: gql.auto
    title: gql.auto
    text: gql.auto
    created: gql.auto
    modified: gql.auto
    creator: User = gql.django.field(select_related="creator__profile")
    comments_enabled: gql.auto
    mentions: List[Optional[User]]
    links: List[Optional[LinkPreview]]

    @gql.field
    def image(self) -> Optional[PostImage]:
        if hasattr(self, "image"):
            return self.image
        return None

    @gql.django.field
    def comments(self, info) -> List[Optional["PostComment"]]:
        current_user = info.context.request.user
        return (
            PostCommentModel.objects.filter(post=self)
            .filter(PostCommentModel.is_visible_query(current_user))
            .filter(UserBlock.not_blocked_query(current_user, "commenter"))
            .order_by("created")
        )

    # this should be removed, once comments are paged
    @gql.django.field
    def number_of_comments(self, info) -> int:
        current_user = info.context.request.user
        return (
            PostCommentModel.objects.filter(post=self)
            .filter(PostCommentModel.is_visible_query(current_user))
            .filter(UserBlock.not_blocked_query(current_user, "commenter"))
            .count()
        )

    @gql.django.field(description="A list of all users involved. Author of the post plus all commenters")
    def involved_users(self, info, offset: int = 0, limit: int = 10) -> Paged[User]:
        current_user = info.context.request.user
        return Paged.of(
            UserModel.objects.select_related("profile")
            .filter(UserModel.is_visible_query(current_user))
            .filter(
                (Q(posts=self) & PostModel.is_visible_query(current_user, "posts"))
                | (Q(posts_comments__post=self) & PostCommentModel.is_visible_query(current_user, "posts_comments"))
            )
            .distinct(),
            offset,
            limit,
        )

    @gql.django.field
    def commenters(self, info, offset: int = 0, limit: int = 10) -> Paged[User]:
        current_user = info.context.request.user
        return Paged.of(
            UserModel.objects.select_related("profile")
            .filter(UserModel.is_visible_query(current_user))
            .filter(Q(posts_comments__post=self) & PostCommentModel.is_visible_query(current_user, "posts_comments"))
            .distinct(),
            offset,
            limit,
        )

    @gql.django.field
    def reactions(self, info) -> ReactionCounts:
        current_user = info.context.request.user
        if current_user.is_anonymous:
            reactions = PostModel.get_reaction_counts_for_post_with_id(self.pk)
        else:
            reactions = current_user.get_reaction_counts_for_post_with_id(self.pk)
        return ReactionCounts(**reactions)

    @gql.django.field(description="Only present, when the current user reacted to this post")
    def my_reaction(self, info) -> ReactionCounts:
        current_user = info.context.request.user
        if not current_user.is_anonymous:
            try:
                reaction = PostReactionModel.objects.filter(post=self, reactor=current_user).first()
                if reaction:
                    return ReactionCounts(**{reaction.reaction_type: 1})
            except PostReactionModel.DoesNotExist:
                return ReactionCounts()
        return ReactionCounts()

    @gql.django.field(prefetch_related="circles")
    def public(self) -> bool:
        return self.is_public_post()


@gql.django.type(CommunityModel)
class Space:
    id: gql.auto
    name: gql.auto
    title: gql.auto
    description: gql.auto
    creator: User
    created: gql.auto
    avatar: str
    avatar_default_color: str
    cover: str
    location: gql.auto
    links: List[Optional[ExternalLink]]
    tasks: List[Optional["Task"]]
    topics: List[Optional[Topic]]
    sdgs: List[Optional[SDG]]
    collaboration_tools: List[Optional[CollaborationTool]]
    contact_description: Optional[str]
    contact_email: Optional[str]
    contact_phone: Optional[str]

    @gql.django.field
    def geolocation(self) -> Optional[Geolocation]:
        return Geolocation.from_point(self.geolocation)

    @gql.django.field(
        description="A list of all active members and their role", prefetch_related="memberships__user__profile"
    )
    def members(self, info, offset: int = 0, limit: int = 10) -> Paged[SpaceMember]:
        return Paged(self.memberships.all()[offset : offset + limit], self.memberships.count())

    @gql.django.field
    def connection_status_to_myself(self, info) -> List[Optional[SpaceUserConnectionType]]:
        current_user: UserModel = info.context.request.user
        if current_user.is_anonymous:
            return []

        roles = []

        if current_user.are_new_post_notifications_enabled_for_community(self):
            roles.append(SpaceUserConnectionType.FOLLOWER)

        if current_user.is_membership_requestor_of_community_with_name(self.name):
            roles.append(SpaceUserConnectionType.MEMBERSHIP_REQUESTOR)

        if self.creator == current_user:
            roles.append(SpaceUserConnectionType.CREATOR)

        if membership := CommunityMembershipModel.objects.filter(community=self, user=current_user).first():
            roles.append(SpaceUserConnectionType.MEMBER)

            if membership.is_administrator:
                roles.append(SpaceUserConnectionType.ADMINISTRATOR)

            # if membership.is_moderator:
            #     roles.append(SpaceUserConnectionType.MODERATOR)

        return roles

    @gql.django.field
    def posts(self, info, offset: int = 0, limit: int = 10, visibility: Visibility = Visibility.ALL) -> Paged[Post]:
        current_user: UserModel = info.context.request.user
        if (
            current_user.is_anonymous
            or not CommunityMembershipModel.objects.filter(community=self, user=current_user).exists()
        ):
            query = PostModel.objects.filter(community=self, circles__id=get_circle_model().get_world_circle_id())
            return Paged.of(query, offset, limit)
        else:
            query = PostModel.objects.filter(community=self)
            if visibility == Visibility.PUBLIC:
                query = query.filter(circles__id=get_circle_model().get_world_circle_id())
            elif visibility == Visibility.PRIVATE:
                query = query.exclude(circles__id=get_circle_model().get_world_circle_id())
            return Paged.of(query, offset, limit)


@gql.django.type(PostCommentModel)
class PostComment:
    id: gql.auto
    text: gql.auto
    creator: User = gql.django.field(field_name="commenter", select_related="commenter__profile")
    created: gql.auto
    modified: gql.auto
    mentions: List[Optional[User]]
    links: List[Optional[LinkPreview]]
    post: Post

    @gql.django.field
    def reactions(self, info) -> ReactionCounts:
        current_user = info.context.request.user
        if current_user.is_anonymous:
            reactions = PostCommentModel.get_reaction_counts_for_post_comment_with_id(self.pk)
        else:
            reactions = current_user.get_reaction_counts_for_post_comment_with_id(self.pk)
        return ReactionCounts(**reactions)

    @gql.django.field(description="Only present, when the current user reacted to this post comment")
    def my_reaction(self, info) -> ReactionCounts:
        current_user = info.context.request.user
        if not current_user.is_anonymous:
            try:
                reaction = PostCommentReactionModel.objects.filter(post_comment=self, reactor=current_user).first()
                if reaction:
                    return ReactionCounts(**{reaction.reaction_type: 1})
            except PostCommentReactionModel.DoesNotExist:
                return ReactionCounts()
        return ReactionCounts()


@gql.type
class NotificationOptions:
    user: Optional[User]
    post: Optional[Post]
    post_comment: Optional[PostComment]
    space: Optional[Space]


@gql.django.type(NotificationModel)
class Notification:
    id: gql.auto
    owner: User
    created: gql.auto
    read: gql.auto
    notification_type: NotificationType

    @gql.django.field
    def options(self) -> Optional[NotificationOptions]:
        options = self.get_options()
        return NotificationOptions(
            user=options.get("user"),
            post=options.get("post"),
            post_comment=options.get("post_comment"),
            space=options.get("space"),
        )


@gql.type
class DiscoverSpaces:
    topic_id: Optional[uuid.UUID] = None
    location: Optional[str] = None
    skill_id: Optional[uuid.UUID] = None
    spaces: Paged[Space]


@gql.type
class MySpaces:
    section: str
    type: SpaceUserConnectionType

    @gql.django.field
    def spaces(self, offset: int = 0, limit: int = 10) -> Paged[Space]:
        """
        When spaces are already resolved, they are returned.
        Otherwise: When a query is provided, it is used to create a paged result.
        """
        # if self.spaces is not None:
        #     return self.spaces
        if hasattr(self, "query"):
            return Paged.of(self.query, offset, limit)
        return Paged()
