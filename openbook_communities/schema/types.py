import logging
import uuid
from typing import TYPE_CHECKING, Annotated, List, Optional, TypeVar

import strawberry
import strawberry_django
from strawberry.file_uploads import Upload

from openbook_auth.models import User as UserModel
from openbook_auth.schema.types import User
from openbook_common.schema.types import GeolocationPoint, GeolocationPointInput, Paged
from openbook_communities.models import CollaborationTool as CollaborationToolModel
from openbook_communities.models import Community as CommunityModel
from openbook_communities.models import CommunityMembership as CommunityMembershipModel
from openbook_communities.models import CommunityMembershipRequest as CommunityMembershipRequestModel
from openbook_communities.models import ExternalLink as ExternalLinkModel
from openbook_communities.models import ExternalLinkType
from openbook_communities.models import OnboardingStep as OnboardingStepModel
from openbook_communities.models import SpaceUserConnectionType
from openbook_communities.models import Task as TaskModel
from openbook_communities.models import VisibilityType
from openbook_posts.enums import VisibilityFilter
from openbook_posts.models import Post as PostModel
from openbook_terms.schema.types import SDG, Skill, Topic

if TYPE_CHECKING:
    from openbook_posts.schema.types import Post

logger = logging.getLogger(__name__)

GenericType = TypeVar("GenericType")


@strawberry.input
class ValidateSpaceInput:
    title: Optional[str] = strawberry.UNSET
    description: Optional[str] = strawberry.UNSET
    topics: Optional[List[Optional[uuid.UUID]]] = strawberry.UNSET
    cover: Optional[Upload] = strawberry.UNSET
    sdgs: Optional[List[Optional[uuid.UUID]]] = strawberry.UNSET
    location: Optional[str] = strawberry.UNSET


@strawberry.input
class CreateSpaceInput:
    title: str
    description: str
    topics: List[Optional[uuid.UUID]]
    cover: Upload


@strawberry.input
class CreateTaskInput:
    space_id: uuid.UUID
    name: str
    description: str
    visibility: VisibilityType
    location_type: TaskModel.LocationType
    regularity: TaskModel.Regularity
    contact_email: str
    slots_available: Optional[int] = strawberry.UNSET
    thumbnail: Optional[Upload] = strawberry.UNSET
    skills: Optional[List[Optional[uuid.UUID]]] = strawberry.UNSET
    location: Optional[str] = strawberry.UNSET
    geolocation: Optional[GeolocationPointInput] = strawberry.UNSET
    contact_phone: Optional[str] = strawberry.UNSET


@strawberry.input
class UpdateTaskInput:
    task_id: uuid.UUID
    space_id: uuid.UUID
    name: str
    description: str
    visibility: VisibilityType
    location_type: TaskModel.LocationType
    regularity: TaskModel.Regularity
    contact_email: str
    slots_available: Optional[int] = strawberry.UNSET
    thumbnail: Optional[Upload] = strawberry.UNSET
    skills: Optional[List[Optional[uuid.UUID]]] = strawberry.UNSET
    location: Optional[str] = strawberry.UNSET
    geolocation: Optional[GeolocationPointInput] = strawberry.UNSET
    contact_phone: Optional[str] = strawberry.UNSET


@strawberry.input
class AddCollaborationToolInput:
    space_id: uuid.UUID
    url: str
    title: str
    description: Optional[str] = strawberry.UNSET
    collection_type: CollaborationToolModel.CollectionType
    thumbnail: Optional[Upload] = strawberry.UNSET


@strawberry.input
class UpdateCollaborationToolInput:
    id: uuid.UUID
    url: Optional[str] = strawberry.UNSET
    title: Optional[str] = strawberry.UNSET
    description: Optional[str] = strawberry.UNSET
    collection_type: Optional[CollaborationToolModel.CollectionType] = strawberry.UNSET
    thumbnail: Optional[Upload] = strawberry.UNSET


@strawberry.input
class AddExternalLinkInput:
    space_id: uuid.UUID
    url: str
    type: ExternalLinkType
    name: str


@strawberry.input
class UpdateExternalLinkInput:
    id: uuid.UUID
    url: Optional[str] = strawberry.UNSET
    type: Optional[ExternalLinkType] = strawberry.UNSET
    name: Optional[str] = strawberry.UNSET


@strawberry_django.type(ExternalLinkModel)
class ExternalLink:
    id: strawberry.auto
    url: strawberry.auto
    type: ExternalLinkType
    name: strawberry.auto


@strawberry.input
class OnboardingStepInput:
    text: str


@strawberry.input
class UpdateSpaceInput:
    id: uuid.UUID
    title: Optional[str] = strawberry.UNSET
    description: Optional[str] = strawberry.UNSET
    topics: Optional[List[Optional[uuid.UUID]]] = strawberry.UNSET
    cover: Optional[Upload] = strawberry.UNSET
    avatar: Optional[Upload] = strawberry.UNSET
    sdgs: Optional[List[Optional[uuid.UUID]]] = strawberry.UNSET
    location: Optional[str] = strawberry.UNSET
    geolocation: Optional[GeolocationPointInput] = strawberry.UNSET
    contact_description: Optional[str] = strawberry.UNSET
    contact_email: Optional[str] = strawberry.UNSET
    contact_phone: Optional[str] = strawberry.UNSET
    onboarding_steps: Optional[List[Optional[OnboardingStepInput]]] = strawberry.UNSET


@strawberry_django.type(CollaborationToolModel)
class CollaborationTool:
    id: strawberry.auto
    url: strawberry.auto
    title: strawberry.auto
    description: strawberry.auto
    collection_type: CollaborationToolModel.CollectionType
    domain: strawberry.auto
    thumbnail: Optional[str]
    thumbnail_blurhash: Optional[str]


@strawberry_django.type(TaskModel)
class Task:
    id: strawberry.auto
    name: strawberry.auto
    description: strawberry.auto
    community: "Space"
    creator: User
    created: strawberry.auto
    slots_available: strawberry.auto
    slots_taken: strawberry.auto
    visibility: VisibilityType
    location_type: TaskModel.LocationType
    location: strawberry.auto
    regularity: TaskModel.Regularity
    skills: List[Skill]
    thumbnail: Optional[str]
    thumbnail_blurhash: Optional[str]
    contact_email: str
    contact_phone: Optional[str]

    @strawberry_django.field()
    def geolocation(self) -> Optional[GeolocationPoint]:
        return GeolocationPoint.from_point(self.geolocation)


@strawberry_django.type(CommunityMembershipModel)
class SpaceMember:
    id: strawberry.auto
    user: User
    community: "Space"
    is_administrator: strawberry.auto
    created: strawberry.auto


@strawberry_django.type(CommunityMembershipRequestModel)
class SpaceMembershipRequest:
    id: strawberry.auto
    user: User
    community: "Space"
    message: strawberry.auto


@strawberry_django.type(OnboardingStepModel)
class OnboardingStep:
    text: Optional[str]


@strawberry.type
class Onboarding:
    steps: List[Optional[OnboardingStep]]


@strawberry_django.type(CommunityModel)
class Space:
    id: strawberry.auto
    name: strawberry.auto
    title: strawberry.auto
    description: strawberry.auto
    creator: Optional[User]
    created: strawberry.auto
    avatar: str
    avatar_blurhash: Optional[str]
    avatar_default_color: str
    cover: str
    cover_blurhash: Optional[str]
    location: strawberry.auto
    links: List[Optional[ExternalLink]]
    tasks: List[Optional["Task"]]
    topics: List[Optional[Topic]]
    sdgs: List[Optional[SDG]]
    contact_description: Optional[str]
    contact_email: Optional[str]
    contact_phone: Optional[str]

    @strawberry_django.field()
    def geolocation(self) -> Optional[GeolocationPoint]:
        return GeolocationPoint.from_point(self.geolocation)

    @strawberry_django.field(
        description="A list of all active members and their role", prefetch_related="memberships__user__profile"
    )
    def members(self, info, offset: int = 0, limit: int = 10) -> Paged[SpaceMember]:
        return Paged(
            self.memberships.all().order_by("-is_administrator", "user__profile__name", "user__profile__last_name")[
                offset : offset + limit
            ],
            self.memberships.count(),
        )

    @strawberry_django.field(
        description="A list of all active membership requests", prefetch_related="membership_requests__user__profile"
    )
    def membership_requests(self, info, offset: int = 0, limit: int = 10) -> Paged[SpaceMembershipRequest]:
        current_user: UserModel = info.context.request.user

        if current_user.is_anonymous or not current_user.is_administrator_of_community_with_id(self.id):
            return Paged([], 0)

        return Paged(
            self.membership_requests.all()[offset : offset + limit],
            self.membership_requests.count(),
        )

    @strawberry_django.field()
    def connection_status_to_myself(self, info) -> List[Optional[SpaceUserConnectionType]]:
        return self.connection_status_to_user(info.context.request.user)

    @strawberry_django.field()
    def posts(
        self, info, offset: int = 0, limit: int = 10, visibility: VisibilityFilter = VisibilityFilter.ALL
    ) -> Paged[Annotated["Post", strawberry.lazy("openbook_posts.schema.types")]]:
        current_user: UserModel = info.context.request.user
        query = PostModel.objects.filter(
            PostModel.is_visible_query(current_user), status=PostModel.STATUS_PUBLISHED, community=self
        )
        if (
            current_user.is_anonymous
            or not CommunityMembershipModel.objects.filter(community=self, user=current_user).exists()
        ):
            query = query.filter(is_public=True)
        else:
            if visibility == VisibilityFilter.PUBLIC:
                query = query.filter(is_public=True)

            elif visibility == VisibilityFilter.MEMBERS:
                query = query.filter(is_public=False)

        return Paged.of(query.order_by("-created"), offset, limit)

    @strawberry_django.field()
    def has_public_posts(self, info) -> bool:
        current_user: UserModel = info.context.request.user
        query = PostModel.objects.filter(
            PostModel.is_visible_query(current_user), status=PostModel.STATUS_PUBLISHED, community=self
        )
        return query.filter(is_public=True).exists()

    @strawberry_django.field()
    def has_private_posts(self, info) -> bool:
        current_user: UserModel = info.context.request.user
        query = PostModel.objects.filter(
            PostModel.is_visible_query(current_user), status=PostModel.STATUS_PUBLISHED, community=self
        )
        return query.filter(is_public=False).exists()

    @strawberry_django.field()
    def onboarding(self, info) -> Optional[Onboarding]:
        onboarding_steps = OnboardingStepModel.objects.filter(
            community=self,
        ).order_by("step_number")

        return Onboarding(steps=onboarding_steps)

    @strawberry_django.field()
    def collaboration_tools(self, info) -> List[Optional[CollaborationTool]]:
        current_user: UserModel = info.context.request.user
        if current_user.is_anonymous or not current_user.is_member_of_community_with_id(self.id):
            return []

        return self.collaboration_tools.all()


@strawberry.type
class DiscoverSpaces:
    spaces: Paged[Space]
    topic_id: Optional[uuid.UUID] = None
    location: Optional[str] = strawberry.field(
        deprecation_reason="Unsupported since version 1.0.16, use location_id instead",
        default=None,
    )
    location_id: Optional[str] = None
    skill_id: Optional[uuid.UUID] = None


@strawberry.type
class MySpaces:
    section: str
    type: SpaceUserConnectionType

    @strawberry_django.field()
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
