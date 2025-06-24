import uuid
from typing import List, Optional

import strawberry
import strawberry_django
import structlog
from django.db.models import F, Q, Value
from django.db.models.functions import Concat
from django.db.models.lookups import IContains

from openbook_auth.models import User as UserModel, UserBlock as UserBlockModel
from openbook_auth.schema.helpers import get_ordered_user_connections
from openbook_auth.schema.types import User, AuthenticatedUser
from openbook_auth.utils import verify_authorized_user
from openbook_common.validators import string_not_empty
from openbook_common.schema.types import Paged

logger = structlog.get_logger(__name__)


@strawberry.type
class Query:
    # TODO HOLI-8088 remove test once get_authenticated_user is removed
    @strawberry_django.field(deprecation_reason="Deprecated in favor of 'authenticatedUserV2'.")
    def authenticated_user(self, info) -> Optional[User]:
        return Query.authenticated_user_v2(self, info)

    @strawberry_django.field()
    def authenticated_user_v2(self, info) -> Optional[AuthenticatedUser]:
        current_user = info.context.request.user
        if current_user.is_anonymous:
            return None
        return current_user

    @strawberry_django.field()
    def user_by_id(self, info, id: uuid.UUID) -> Optional[User]:
        current_user = info.context.request.user
        user = UserModel.objects.filter(UserModel.is_visible_ignore_blocked_query()).get(username=id)
        return UserBlockModel.filter_single_object(current_user, user, lambda u: u.id)

    @strawberry_django.field()
    def users_by_chat_identities(self, info, identities: List[str], offset: int = 0, limit: int = 10) -> Paged[User]:
        current_user = verify_authorized_user(info)
        users = UserModel.objects.filter(Q(identity__in=identities) & UserModel.is_visible_ignore_blocked_query())
        return UserBlockModel.paged(current_user, lambda u: u.id, users, offset, limit)

    @strawberry_django.field()
    def user_by_name(self, info, substring: str, offset: int = 0, limit: int = 5) -> Paged[User]:
        string_not_empty(substring)

        current_user = info.context.request.user
        users_to_exclude_ids = [current_user.id] if not current_user.is_anonymous else []
        excludes_filter = ~Q(id__in=users_to_exclude_ids) & UserModel.is_visible_ignore_blocked_query()
        full_name_query = (
            IContains(
                Concat(F("profile__name"), Value(" "), F("profile__last_name")),
                substring,
            )
            & excludes_filter
        )

        total_results = UserModel.objects.filter(full_name_query).count()

        by_first_name_query = (
            UserModel.objects.select_related("profile")
            .filter(Q(profile__name__icontains=substring) & excludes_filter)
            .order_by("profile__name", "profile__last_name", "profile__id")
        )
        by_first_name = UserBlockModel.filter_blocked_objects(
            current_user, lambda user: user.id, by_first_name_query, offset, limit
        )

        by_first_name_len = len(by_first_name)

        if by_first_name_len >= limit:  # we have more users than we are looking for
            return Paged(by_first_name, total_results)

        if by_first_name_len > 0:  # we have some users, but not enough
            new_offset = 0
            new_limit = limit - by_first_name_len
        else:
            new_offset = offset - by_first_name_query.count()
            new_limit = limit

        by_full_name = UserBlockModel.filter_blocked_objects(
            current_user,
            lambda user: user.id,
            UserModel.objects.select_related("profile")
            .filter(full_name_query & ~Q(profile__name__icontains=substring))
            .order_by("profile__name", "profile__last_name", "profile__id"),
            new_offset,
            new_limit,
        )

        return Paged(by_first_name + by_full_name, total_results)

    @strawberry_django.field()
    def connected_users(self, info, offset: int = 0, limit: int = 10) -> Paged[User]:
        current_user = verify_authorized_user(info)

        return Paged.of(current_user.connected_users(), offset, limit)

    @strawberry_django.field()
    def my_connections(self, info, offset: int = 0, limit: int = 10) -> Paged[User]:
        current_user = verify_authorized_user(info)
        return get_ordered_user_connections(circle_id=current_user.connections_circle_id, offset=offset, limit=limit)

    @strawberry_django.field()
    def connections_by_user_id(self, info, user_id: uuid.UUID, offset: int = 0, limit: int = 10) -> Paged[User]:
        verify_authorized_user(info)
        user = UserModel.objects.get(username=user_id)
        return get_ordered_user_connections(circle_id=user.connections_circle_id, offset=offset, limit=limit)
