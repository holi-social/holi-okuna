import uuid
from datetime import datetime, timedelta
from typing import Generic, List, Optional, TypeVar
from django.utils.translation import get_language_from_request

import strawberry
import strawberry_django
import structlog
from django.db.models import F, Q, Value
from django.db.models.functions import Concat
from django.db.models.lookups import IContains
from graphql import GraphQLError

from openbook_auth.models import User as UserModel
from openbook_auth.schema.types import User
from openbook_auth.utils import verify_authorized_user
from openbook_common.validators import string_not_empty
from openbook.graphql_errors import GraphQLErrorCodes
from openbook_common.schema.types import Paged
from openbook_notifications.api import NotificationApi

logger = structlog.get_logger(__name__)


@strawberry.type
class Query:
    @strawberry_django.field()
    def authenticated_user(self, info) -> Optional[User]:
        current_user = info.context.request.user
        if current_user.is_anonymous:
            return None
        locale = get_language_from_request(info.context.request)
        NotificationApi.find_or_create_subscriber(user=current_user, locale=locale)

        # TODO: This is a hack to make sure that the subscriber is updated with the correct locale.
        # Remove this when we add a language picker to the user profile.
        NotificationApi.update_subscriber(user=current_user, locale=locale)

        return current_user

    @strawberry_django.field()
    def user_by_id(self, info, id: uuid.UUID) -> Optional[User]:
        try:
            current_user = info.context.request.user
            return UserModel.objects.filter(UserModel.is_visible_query(current_user)).get(username=id)
        except UserModel.DoesNotExist:
            raise GraphQLError("User not found", extensions={"code": GraphQLErrorCodes.NOT_FOUND})

    @strawberry_django.field()
    def users_by_chat_identities(self, info, identities: List[str], offset: int = 0, limit: int = 10) -> Paged[User]:
        current_user = verify_authorized_user(info)
        users = UserModel.objects.filter(Q(identity__in=identities) & UserModel.is_visible_query(current_user))

        return Paged.of(users, offset, limit)

    @strawberry_django.field()
    def user_by_name(self, info, substring: str, offset: int = 0, limit: int = 5) -> Paged[User]:
        string_not_empty(substring)

        current_user = info.context.request.user
        users_to_exclude_ids = [current_user.id] if not current_user.is_anonymous else []
        excludes_filter = ~Q(id__in=users_to_exclude_ids) & UserModel.is_visible_query(current_user)
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
            .order_by("profile__name", "profile__last_name")
        )
        by_first_name = list(by_first_name_query[offset : offset + limit])
        by_first_name_len = len(by_first_name)

        if by_first_name_len >= limit:
            return Paged(by_first_name, total_results)

        if by_first_name_len > 0:
            new_offset = 0
            new_limit = limit - by_first_name_len
        else:
            new_offset = offset - by_first_name_query.count()
            new_limit = limit

        by_full_name = list(
            UserModel.objects.select_related("profile")
            .filter(full_name_query & ~Q(profile__name__icontains=substring))
            .order_by("profile__name", "profile__last_name")[new_offset : new_offset + new_limit]
        )
        return Paged(by_first_name + by_full_name, total_results)

    @strawberry_django.field()
    def user_suggestions(self, info, offset: int = 0, limit: int = 10) -> Paged[User]:
        current_user = info.context.request.user
        query = (
            UserModel.objects.select_related("profile")
            .filter(UserModel.is_visible_query(current_user))
            .filter(date_joined__lte=datetime.now() - timedelta(hours=1))
            .order_by("-date_joined")
        )
        if current_user.id:
            query = query.exclude(id=current_user.id)
        return Paged.of(
            query,
            offset,
            limit,
        )
