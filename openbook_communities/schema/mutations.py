import uuid
from typing import Optional

import strawberry
import structlog
from asgiref.sync import sync_to_async
from django.db import transaction
from graphql import GraphQLError

from django.contrib.contenttypes.models import ContentType as ContentTypeModel
from favorites.models import UserFavorite as UserFavoriteModel, FavoritableType
from openbook.graphql_errors import GraphQLErrorCodes
from openbook_common.enums import VisibilityType
from openbook_common.utils.model_loaders import get_community_model
from openbook_communities.events import (
    publish_space_created_event,
    publish_space_updated_event,
    publish_space_user_added_event,
    publish_space_deleted_event,
    publish_space_user_left_event,
    publish_space_user_removed_event,
    publish_task_created_event,
    publish_task_updated_event,
    publish_task_deleted_event,
)
from openbook.utils import invalidate_discover_spaces_query_cache
from openbook_auth.models import User as UserModel
from openbook_auth.schema.types import UpdateConnectionAction
from openbook_auth.utils import verify_authorized_user
from openbook_common.helpers import is_parameter_null, to_input_dict
from openbook_common.schema.types import GeolocationPointInput, Result
from openbook_communities.models import Community as CommunityModel
from openbook_communities.models import Task as TaskModel
from openbook_communities.models import SpaceUserConnectionType
from openbook_communities.models.completed_task import CompletedTask as CompletedTaskModel
from openbook_communities.schema.types import (
    AddCollaborationToolInput,
    AddExternalLinkInput,
    CollaborationTool,
    CreateSpaceInput,
    CreateTaskInput,
    ExternalLink,
    Space,
    Task,
    UpdateCollaborationToolInput,
    UpdateExternalLinkInput,
    UpdateSpaceInput,
    UpdateTaskInput,
    ValidateSpaceInput,
    CompletedTask,
)
from openbook_communities.serializers.communities_serializers import (
    AddCollaborationToolSerializer,
    AddExternalLinkSerializer,
    CreateCommunitySerializer,
    CreateTaskSerializer,
    InviteToCommunityByEmailSerializer,
    UpdateCollaborationToolSerializer,
    UpdateCommunitySerializer,
    UpdateExternalLinkSerializer,
    UpdateTaskSerializer,
    ValidateCommunitySerializer,
)
from openbook_communities.serializers.community_serializers import (
    CommunityUserConnectionSerializer,
)
from openbook_common.tracking import track, TrackingEvent

logger = structlog.get_logger(__name__)


@strawberry.type
class Mutation:
    @strawberry.mutation(description="When no userId is provided, the logged in user is used instead.")
    @sync_to_async
    def update_space_user_connection(
        self,
        info,
        space_id: uuid.UUID,
        connection_type: SpaceUserConnectionType,
        connect_action: UpdateConnectionAction,
        user_id: Optional[uuid.UUID] = None,
        message: Optional[str] = None,
    ) -> Space:
        current_user = verify_authorized_user(info)

        serializer = CommunityUserConnectionSerializer(data={"community_id": space_id, "message": message})
        serializer.is_valid(raise_exception=True)

        space = CommunityModel.objects.get(id=space_id)

        ConnectionType = SpaceUserConnectionType
        Action = UpdateConnectionAction
        UserFavorite = UserFavoriteModel
        Task = TaskModel

        invalidate_discover_spaces_query_cache()

        if not user_id or current_user.username == user_id:
            # perform for current user
            match (connection_type, connect_action):
                # user requests membership in space
                case (ConnectionType.MEMBERSHIP_REQUESTOR, Action.CONNECT):
                    return current_user.request_membership_to_community_with_name(space.name, message)
                # user revokes membership request
                case (ConnectionType.MEMBERSHIP_REQUESTOR, Action.DISCONNECT):
                    return current_user.revoke_membership_request_to_community_with_name(space.name)
                # user accepts invitation to space
                case (ConnectionType.MEMBERSHIP_INVITEE, Action.CONNECT):
                    space = current_user.accept_membership_invite_to_community_for_username(space.name)
                    publish_space_user_added_event(username=str(current_user.username), community=space)
                    return space
                # user rejects invitation to space
                case (ConnectionType.MEMBERSHIP_INVITEE, Action.DISCONNECT):
                    return current_user.reject_membership_invite_to_community_for_username(space.name)
                # user follows a space
                case (ConnectionType.FOLLOWER, Action.CONNECT):
                    return current_user.enable_new_post_notifications_for_community_with_name(space.name)
                # user unfollows a space
                case (ConnectionType.FOLLOWER, Action.DISCONNECT):
                    return current_user.disable_new_post_notifications_for_community_with_name(space.name)
                # user leaves space or is removed by space admin
                case (ConnectionType.MEMBER | ConnectionType.ADMINISTRATOR, Action.LEAVE_SPACE):
                    community_to_leave: CommunityModel = current_user.leave_community_with_name(space.name)
                    # Remove the user as the organizer of the appointments they have created in this space
                    community_to_leave.appointments.filter(creator=current_user).update(creator=None)
                    community_to_leave.delete_pending_notifications_for_user(current_user.username)
                    UserFavorite.delete_multiple_favorites_of_user(
                        Task.private_task_ids_of_community(community=community_to_leave), current_user
                    )
                    publish_space_user_left_event(user=current_user, community=community_to_leave)
                    return community_to_leave
                case _:
                    raise GraphQLError("Operation not allowed", extensions={"code": GraphQLErrorCodes.FORBIDDEN})
        else:
            # perform for other user
            match (connection_type, connect_action):
                # space admin rejected membership request
                case (ConnectionType.MEMBERSHIP_REQUESTOR, Action.DISCONNECT):
                    return current_user.revoke_membership_request_to_community_for_username(user_id, space.name)
                # space admin accepted membership request
                case (ConnectionType.MEMBER, Action.CONNECT):
                    space = current_user.approve_membership_request_to_community_for_username(user_id, space.name)
                    publish_space_user_added_event(username=str(user_id), community=space)
                    return space
                # space admin invites user
                case (ConnectionType.MEMBERSHIP_INVITEE, Action.CONNECT):
                    return current_user.invite_to_community(username=str(user_id), community=space)
                # space admin withdraws membership invite
                case (ConnectionType.MEMBERSHIP_INVITEE, Action.DISCONNECT):
                    current_user.uninvite_user_with_username_to_community_with_name(
                        username=str(user_id), community_name=space.name
                    )
                    return space
                # space admin grants admin rights to another user
                case (ConnectionType.ADMINISTRATOR, Action.GRANT_ADMIN_ACCESS):
                    return current_user.add_administrator_with_username_to_community_with_name(user_id, space.name)
                # space admin revokes admin rights from another user
                case (ConnectionType.ADMINISTRATOR, Action.REVOKE_ADMIN_ACCESS):
                    space.delete_pending_notifications_for_user(user_id)
                    return current_user.remove_administrator_with_username_from_community_with_name(
                        user_id, space.name
                    )
                # space admin removes member
                case (ConnectionType.ADMINISTRATOR, Action.REMOVE_MEMBER):
                    space.delete_pending_notifications_for_user(user_id)
                    community = current_user.remove_member_from_community(user_id, space.name)
                    user_to_remove = UserModel.objects.get(username=user_id)
                    UserFavorite.delete_multiple_favorites_of_user(
                        Task.private_task_ids_of_community(community=community), user_to_remove
                    )
                    publish_space_user_removed_event(user=user_to_remove, community=community)
                    return community
                case _:
                    raise GraphQLError(
                        "Operation not allowed",
                        extensions={"code": GraphQLErrorCodes.FORBIDDEN},
                    )

    @strawberry.mutation
    @sync_to_async
    def validate_space(self, info, input: ValidateSpaceInput) -> Result:
        verify_authorized_user(info)

        serializer = ValidateCommunitySerializer(data=to_input_dict(input))
        serializer.is_valid(raise_exception=True)

        return Result(success=True)

    @strawberry.mutation
    @sync_to_async
    def create_space(self, info, input: CreateSpaceInput) -> Space:
        current_user = verify_authorized_user(info)

        serializer = CreateCommunitySerializer(data=to_input_dict(input))
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        with transaction.atomic():
            space = current_user.create_community(
                title=data.get("title"),
                type=CommunityModel.COMMUNITY_TYPE_PUBLIC,
                description=data.get("description"),
                cover=data.get("cover"),
                invites_enabled=True,
                topics_v2=data.get("topics_v2"),
            )

        publish_space_created_event(community=space)
        track(current_user, TrackingEvent("spaceCreated", {"spaceId": str(space.id)}))
        invalidate_discover_spaces_query_cache()

        return space

    @strawberry.mutation
    @sync_to_async
    def update_space(self, info, input: UpdateSpaceInput) -> Space:
        current_user = verify_authorized_user(info)

        serializer = UpdateCommunitySerializer(data=to_input_dict(input))
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        Community = get_community_model()
        space = Community.objects.get(id=data.get("id"))

        space = current_user.update_community(
            community=space,
            title=data.get("title"),
            description=data.get("description"),
            topics_v2=data.get("topics_v2"),
            cover=data.get("cover"),
            remove_cover=is_parameter_null(data, "cover"),
            avatar=data.get("avatar"),
            remove_avatar=is_parameter_null(data, "avatar"),
            sdg_ids=data.get("sdgs"),
            location=data.get("location"),
            geolocation=(GeolocationPointInput.to_point(data.get("geolocation"))),
            contact_description=data.get("contact_description"),
            contact_email=data.get("contact_email"),
            contact_phone=data.get("contact_phone"),
            onboarding_steps=data.get("onboarding_steps"),
        )

        # if space details are updated this can have consequences for its tasks (e.g. classifications & recommendations)
        # publishing an update event for all tasks makes sure that downstream systems can update themselves accordingly
        for task in space.tasks.all():
            publish_task_updated_event(user=current_user, task=task)

        publish_space_updated_event(community=space)
        track(current_user, TrackingEvent("spaceUpdated", {"spaceId": str(space.id)}))
        invalidate_discover_spaces_query_cache()

        return space

    @strawberry.mutation
    @sync_to_async
    def delete_space(self, info, id: uuid.UUID) -> Result:
        current_user = verify_authorized_user(info)
        try:
            space = CommunityModel.objects.get(id=id)
            tasks = list(TaskModel.objects.filter(deleted_at=None, community_id=id).all())

            with transaction.atomic():
                space.delete_pending_notifications()
                current_user.delete_community_with_id(
                    community_id=id,
                )

            for task in tasks:
                publish_task_deleted_event(current_user, task)
            publish_space_deleted_event(space)
            track(current_user, TrackingEvent("spaceDeleted", {"spaceId": str(space.id)}))
            invalidate_discover_spaces_query_cache()

        except CommunityModel.DoesNotExist:
            # the space does not exist in the first place, which is just as good as deleting it
            Result(success=True)

        return Result(success=True)

    @strawberry.mutation
    @sync_to_async
    def invite_to_space_by_email(self, info, email: str, space_id: uuid.UUID) -> Result:
        current_user = verify_authorized_user(info)
        current_user_language = info.context.request.META.get("HTTP_ACCEPT_LANGUAGE")

        serializer = InviteToCommunityByEmailSerializer(data={"email": email, "space_id": space_id})
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        current_user.invite_to_community_by_email(
            email=data.get("email"), space_id=data.get("space_id"), language=current_user_language
        )

        return Result(success=True)

    @strawberry.mutation
    @sync_to_async
    def create_task(self, info, input: CreateTaskInput) -> Task:
        current_user = verify_authorized_user(info)

        serializer = CreateTaskSerializer(data=to_input_dict(input))
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        space_id = data.get("space_id")
        duration = data.get("duration", TaskModel.Duration.INDETERMINATE)
        interaction_type = data.get("interaction_type", TaskModel.InteractionType.CHAT)

        with transaction.atomic():
            task = current_user.create_task(
                space_id=space_id,
                name=data.get("name"),
                description=data.get("description"),
                impact=data.get("impact"),
                slots_available=data.get("slots_available"),
                visibility=data.get("visibility"),
                location_type=data.get("location_type"),
                location=data.get("location"),
                geolocation=(GeolocationPointInput.to_point(data.get("geolocation"))),
                regularity=data.get("regularity"),
                duration=duration,
                interaction_type=interaction_type,
                timeframe_start_date=data.get("timeframe_start_date"),
                timeframe_end_date=data.get("timeframe_end_date"),
                contact_email=data.get("contact_email"),
                contact_phone=data.get("contact_phone"),
                skills_v2=data.get("skills_v2"),
                thumbnail=data.get("thumbnail"),
                interaction_signup_link=data.get("interaction_signup_link"),
            )

        publish_task_created_event(current_user, task)
        track(
            current_user,
            TrackingEvent("taskCreated", {"spaceId": str(space_id), "taskId": str(task.id)}),
        )

        return task

    @strawberry.mutation
    @sync_to_async
    def update_task(self, info, input: UpdateTaskInput) -> Task:
        current_user = verify_authorized_user(info)

        serializer = UpdateTaskSerializer(data=to_input_dict(input))
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        space_id = data.get("space_id")
        task_id = data.get("task_id")
        duration = data.get("duration", TaskModel.Duration.INDETERMINATE)
        interaction_type = data.get("interaction_type", TaskModel.InteractionType.CHAT)

        initial_task_visibility = TaskModel.objects.get(id=task_id).visibility
        update_makes_task_private = (
            initial_task_visibility == VisibilityType.PUBLIC and data.get("visibility") != VisibilityType.PUBLIC
        )

        with transaction.atomic():
            task = current_user.update_task(
                task_id=task_id,
                space_id=space_id,
                name=data.get("name"),
                description=data.get("description"),
                impact=data.get("impact"),
                slots_available=data.get("slots_available"),
                visibility=data.get("visibility"),
                location_type=data.get("location_type"),
                location=data.get("location"),
                geolocation=(GeolocationPointInput.to_point(data.get("geolocation"))),
                regularity=data.get("regularity"),
                duration=duration,
                interaction_type=interaction_type,
                timeframe_start_date=data.get("timeframe_start_date"),
                timeframe_end_date=data.get("timeframe_end_date"),
                contact_email=data.get("contact_email"),
                contact_phone=data.get("contact_phone"),
                skills_v2=data.get("skills_v2"),
                thumbnail=data.get("thumbnail"),
                remove_thumbnail=is_parameter_null(data, "thumbnail"),
                interaction_signup_link=data.get("interaction_signup_link"),
            )

        publish_task_updated_event(current_user, task)
        track(
            current_user,
            TrackingEvent("taskUpdated", {"spaceId": str(space_id), "taskId": str(task.id)}),
        )

        if update_makes_task_private:
            task_content_type = ContentTypeModel.objects.filter(model=FavoritableType.TASK).first()
            UserFavoriteModel.objects.filter(favoritable_id=task_id, favoritable_type=task_content_type.id).delete()

        return task

    @strawberry.mutation
    @sync_to_async
    def delete_task(self, info, id: uuid.UUID) -> Result:
        current_user = verify_authorized_user(info)

        with transaction.atomic():
            task = current_user.delete_task_with_id(task_id=id)

        publish_task_deleted_event(current_user, task)
        track(
            current_user,
            TrackingEvent("taskDeleted", {"spaceId": str(task.community_id), "taskId": str(task.id)}),
        )

        return Result(success=True)

    @strawberry.mutation
    @sync_to_async
    def add_collaboration_tool(self, info, input: AddCollaborationToolInput) -> CollaborationTool:
        current_user = verify_authorized_user(info)

        serializer = AddCollaborationToolSerializer(data=to_input_dict(input))
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        return current_user.add_collaboration_tool(
            space_id=data.get("space_id"),
            url=data.get("url"),
            title=data.get("title"),
            description=data.get("description"),
            collection_type=data.get("collection_type"),
            thumbnail=data.get("thumbnail"),
        )

    @strawberry.mutation
    @sync_to_async
    def update_collaboration_tool(self, info, input: UpdateCollaborationToolInput) -> CollaborationTool:
        current_user = verify_authorized_user(info)

        serializer = UpdateCollaborationToolSerializer(data=to_input_dict(input))
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        return current_user.update_collaboration_tool(
            collaboration_tool_id=data.get("id"),
            url=data.get("url"),
            title=data.get("title"),
            description=data.get("description"),
            collection_type=data.get("collection_type"),
            thumbnail=data.get("thumbnail"),
            remove_thumbnail=is_parameter_null(data, "thumbnail"),
        )

    @strawberry.mutation
    @sync_to_async
    def delete_collaboration_tool(self, info, id: uuid.UUID) -> Result:
        current_user = verify_authorized_user(info)

        with transaction.atomic():
            current_user.delete_collaboration_tool(
                collaboration_tool_id=id,
            )

        return Result(success=True)

    @strawberry.mutation
    @sync_to_async
    def add_external_link(self, info, input: AddExternalLinkInput) -> ExternalLink:
        current_user = verify_authorized_user(info)

        serializer = AddExternalLinkSerializer(data=to_input_dict(input))
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        return current_user.add_external_link(
            space_id=data.get("space_id"),
            url=data.get("url"),
            type=data.get("type"),
            name=data.get("name"),
        )

    @strawberry.mutation
    @sync_to_async
    def update_external_link(self, info, input: UpdateExternalLinkInput) -> ExternalLink:
        current_user = verify_authorized_user(info)

        serializer = UpdateExternalLinkSerializer(data=to_input_dict(input))
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        return current_user.update_external_link(
            external_link_id=data.get("id"),
            url=data.get("url"),
            type=data.get("type"),
            name=data.get("name"),
        )

    @strawberry.mutation
    @sync_to_async
    def delete_external_link(self, info, id: uuid.UUID) -> Result:
        current_user = verify_authorized_user(info)

        with transaction.atomic():
            current_user.delete_external_link(
                external_link_id=id,
            )

        return Result(success=True)

    @strawberry.mutation
    @sync_to_async
    def complete_ready_to_go_task(self, info, id: uuid.UUID) -> CompletedTask:
        current_user = verify_authorized_user(info)

        task = TaskModel.objects.filter(id=id).first()
        if not task:
            raise GraphQLError("Task not found", extensions={"code": GraphQLErrorCodes.NOT_FOUND})

        is_permitted = (
            TaskModel.objects.filter(id=id)
            .filter(TaskModel.is_visible_query(current_user) & TaskModel.is_not_expired_query())
            .exists()
        )

        if not is_permitted:
            raise GraphQLError(
                "You don't have permission to access this task or it has expired",
                extensions={"code": GraphQLErrorCodes.FORBIDDEN},
            )

        is_ready_to_go = task.interaction_type == TaskModel.InteractionType.READY

        if not is_ready_to_go:
            raise GraphQLError(
                "Only tasks with 'Ready to Go' interaction type can be completed",
                extensions={"code": GraphQLErrorCodes.FORBIDDEN},
            )

        with transaction.atomic():
            completed_task = CompletedTaskModel.objects.create(task_id=id, user=current_user)

        return completed_task
