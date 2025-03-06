import logging
import uuid
from typing import Annotated, List, Optional, TypeVar, TypeAlias, Any

import strawberry
import strawberry_django
from django.db.models import Q
from django.utils import timezone
from strawberry.django.context import StrawberryDjangoContext
from strawberry.file_uploads import Upload
from strawberry.types import Info as StrawberryInfo

from openbook_appointments.schema.types import Appointment
from openbook_auth.models import User as UserModel
from openbook_auth.schema.types import User
from openbook_common.schema.types import GeolocationPoint, GeolocationPointInput, Paged, GeoJSON
from openbook_communities.helpers import get_space_representatives
from openbook_communities.models import (
    CollaborationTool as CollaborationToolModel,
    Community,
    Community as CommunityModel,
    CommunityMembership as CommunityMembershipModel,
    CommunityMembershipRequest as CommunityMembershipRequestModel,
    CommunityInvite as CommunityInviteModel,
    ExternalLink as ExternalLinkModel,
    ExternalLinkType,
    OnboardingStep as OnboardingStepModel,
    SpaceUserConnectionType,
    Task as TaskModel,
    VisibilityType,
)
from openbook_communities.models.network_relationship import (
    SpacesRelationship as SpacesRelationshipModel,
    SpacesRelationshipType,
)
from openbook_posts.enums import VisibilityFilter
from openbook_posts.models import Post as PostModel
from openbook_posts.schema.types import Post
from openbook_terms.schema.types import SDG, Skill, Topic

logger = logging.getLogger(__name__)

GenericType = TypeVar("GenericType")
Info: TypeAlias = StrawberryInfo[StrawberryDjangoContext, Any]


@strawberry.input
class ValidateSpaceInput:
    title: Optional[str] = strawberry.UNSET
    description: Optional[str] = strawberry.UNSET
    topics: Annotated[
        Optional[List[Optional[uuid.UUID]]],
        strawberry.argument(description="Deprecated since 1.52. Use topics_v2 instead."),
    ] = strawberry.UNSET
    topics_v2: Optional[List[str]] = strawberry.UNSET
    cover: Optional[Upload] = strawberry.UNSET
    sdgs: Optional[List[Optional[uuid.UUID]]] = strawberry.UNSET
    location: Optional[str] = strawberry.UNSET


@strawberry.input
class CreateSpaceInput:
    title: str
    description: str
    topics: Annotated[
        Optional[List[Optional[uuid.UUID]]],
        strawberry.argument(description="Deprecated since 1.52. Use topics_v2 instead."),
    ] = strawberry.UNSET
    topics_v2: Optional[List[str]] = strawberry.UNSET
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
    skills: Annotated[
        Optional[List[Optional[uuid.UUID]]],
        strawberry.argument(description="Deprecated since 1.52. Use skills_v2 instead."),
    ] = strawberry.UNSET
    skills_v2: Optional[List[str]] = strawberry.UNSET
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
    skills: Annotated[
        Optional[List[Optional[uuid.UUID]]],
        strawberry.argument(description="Deprecated since 1.52. Use skills_v2 instead."),
    ] = strawberry.UNSET
    skills_v2: Optional[List[str]] = strawberry.UNSET
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
    topics: Annotated[
        Optional[List[Optional[uuid.UUID]]],
        strawberry.argument(description="Deprecated since 1.52. Use topics_v2 instead."),
    ] = strawberry.UNSET
    topics_v2: Optional[List[str]] = strawberry.UNSET
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
    space: "Space" = strawberry_django.field(field_name="community")
    creator: User
    created: strawberry.auto
    slots_available: strawberry.auto
    slots_taken: strawberry.auto
    visibility: VisibilityType
    location_type: TaskModel.LocationType
    location: strawberry.auto
    regularity: TaskModel.Regularity
    skills: List[Skill] = strawberry_django.field(
        deprecation_reason="Deprecated since version 1.52, use skills_v2 instead.", default=None
    )
    skills_v2: List[str]
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


@strawberry_django.type(CommunityInviteModel)
class SpaceInvite:
    id: strawberry.auto
    community: "Space"
    invited_user: User
    creator: User


@strawberry_django.type(SpacesRelationshipModel)
class SpacesRelationship:
    id: strawberry.auto
    from_space: "Space"
    relationship_type: strawberry.auto
    to_space: "Space"


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
    avatar: Optional[str]
    avatar_blurhash: Optional[str]
    avatar_default_color: str
    cover: Optional[str]
    cover_blurhash: Optional[str]
    location: strawberry.auto
    links: List[Optional[ExternalLink]]
    topics: List[Optional[Topic]] = strawberry_django.field(
        deprecation_reason="Deprecated since version 1.52, use topics_v2 instead.", default=None
    )
    topics_v2: List[str]
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
            self.memberships.all().order_by(
                "-is_administrator", "user__profile__name", "user__profile__last_name", "user__profile__id"
            )[offset : offset + limit],
            self.memberships.count(),
        )

    @strawberry_django.field(description="A list of space members that can be contacted for information.")
    def representatives(self) -> list[SpaceMember]:
        return list(get_space_representatives(self))

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

    @strawberry_django.field(
        description="A list of all active invites to this space", prefetch_related="invites__invited_user__profile"
    )
    def invites(self, info, offset: int = 0, limit: int = 10) -> Paged[SpaceInvite]:
        current_user: UserModel = info.context.request.user

        if current_user.is_anonymous or not current_user.is_administrator_of_community_with_id(self.id):
            return Paged([], 0)

        return Paged(
            self.invites.all()[offset : offset + limit],
            self.invites.count(),
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

        return Paged.of(query.distinct().order_by("-created"), offset, limit)

    @strawberry_django.field()
    def has_public_posts(self, info) -> bool:
        current_user: UserModel = info.context.request.user
        return (
            PostModel.objects.filter(
                PostModel.is_visible_query(current_user), status=PostModel.STATUS_PUBLISHED, community=self
            )
            .filter(is_public=True)
            .exists()
        )

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

    @strawberry_django.field()
    def appointments(self, info, offset: int = 0, limit: int = 10) -> Paged[Appointment]:
        current_user: UserModel = info.context.request.user
        current_datetime = timezone.now()

        # Check if the user is anonymous or not a member of the space
        if current_user.is_anonymous or not current_user.is_member_of_community_with_id(self.id):
            # Retrieve upcoming public appointments
            public_appointments = self.appointments.filter(
                invite_only=False, end_date_time__gte=current_datetime, is_deleted=False
            ).order_by("start_date_time")

            return Paged.of(public_appointments, offset, limit)

        # If the user is a member of the space, retrieve all upcoming appointments
        appointments = self.appointments.filter(end_date_time__gte=current_datetime, is_deleted=False).order_by(
            "start_date_time"
        )

        return Paged.of(appointments, offset, limit)

    @strawberry_django.field()
    def parent_space(self) -> Optional["Space"]:
        """
        We currently assume that a space can only have one parent.
        There is no technical limitation for this, however, a Space can have multiple
        different parent-child relationships/be part of different hierarchies.
        """
        return Community.objects.filter(
            space_relationships__to_space=self, space_relationships__relationship_type=SpacesRelationshipType.PARENT_OF
        ).first()

    @strawberry_django.field()
    def child_spaces(
        self, info, geolocation: Optional[GeoJSON] = None, offset: int = 0, limit: int = 10
    ) -> Paged["Space"]:
        query = Q(
            space_relationships__to_space=self, space_relationships__relationship_type=SpacesRelationshipType.PART_OF
        )

        if geolocation is not None:
            query.add(Q(geolocation__within=geolocation.geometry), Q.AND)

        return Paged.of(
            Community.objects.filter(query),
            offset,
            limit,
        )

    @strawberry_django.field()
    def tasks(self, info: Info) -> list[Task]:
        current_user: UserModel = info.context.request.user
        return TaskModel.objects.filter(community=self).filter(TaskModel.is_visible_query(current_user)).distinct()


@strawberry.type
class DiscoverSpaces:
    spaces: Paged[Space]
    topic_id: Optional[uuid.UUID] = strawberry.field(
        deprecation_reason="Deprecated since version 1.52, use topic_v2 instead", default=None
    )
    topic_v2: Optional[str] = None
    location: Optional[str] = strawberry.field(
        deprecation_reason="Deprecated since version 1.0.16, use location_id instead",
        default=None,
    )
    location_id: Optional[str] = None
    skill_id: Optional[uuid.UUID] = strawberry.field(
        deprecation_reason="Deprecated since version 1.52, use skill_v2 instead",
        default=None,
    )
    skill_v2: Optional[str] = None


@strawberry.type
class MySpaces:
    section: str
    type: SpaceUserConnectionType

    @strawberry_django.field()
    def spaces(self, offset: int = 0, limit: int = 10) -> Paged[Space]:
        if hasattr(self, "query"):
            return Paged.of(self.query, offset, limit)
        return Paged()
