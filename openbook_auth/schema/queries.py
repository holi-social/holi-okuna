import uuid
from datetime import datetime, timedelta

from django.db.models import F, Q, Value
from django.db.models.functions import Concat
from django.db.models.lookups import IContains
from graphql import GraphQLError
from strawberry_django_plus import gql

from openbook.graphql_errors import GraphQLErrorCodes
from openbook.graphql_types import Paged
from openbook_auth import models as auth_models
from openbook_auth import validators as auth_validators
from openbook_auth.schema import types as auth_types


@gql.type
class Query:
    @gql.django.field
    def authenticated_user(self, info) -> auth_types.User | None:
        current_user = info.context.request.user
        return None if current_user.is_anonymous else current_user

    @gql.django.field
    def user_by_id(self, info, id: uuid.UUID) -> auth_types.User | None:
        try:
            current_user = info.context.request.user
            return auth_models.User.objects.filter(auth_models.User.is_visible_query(current_user)).get(username=id)
        except auth_models.User.DoesNotExist:
            raise GraphQLError("User not found", extensions={"code": GraphQLErrorCodes.NOT_FOUND})

    @gql.django.field
    def user_by_name(self, info, substring: str, offset: int = 0, limit: int = 5) -> Paged[auth_types.User]:
        auth_validators.string_not_empty(substring)

        current_user = info.context.request.user
        users_to_exclude_ids = [current_user.id] if not current_user.is_anonymous else []
        excludes_filter = ~Q(id__in=users_to_exclude_ids) & auth_models.User.is_visible_query(current_user)
        full_name_query = (
            IContains(
                Concat(F("profile__name"), Value(" "), F("profile__last_name")),
                substring,
            )
            & excludes_filter
        )

        total_results = auth_models.User.objects.filter(full_name_query).count()

        by_first_name_query = auth_models.User.objects.select_related("profile").filter(
            Q(profile__name__icontains=substring) & excludes_filter
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
            auth_models.User.objects.select_related("profile").filter(
                full_name_query & ~Q(profile__name__icontains=substring)
            )[new_offset : new_offset + new_limit]
        )
        return Paged(by_first_name + by_full_name, total_results)

    @gql.django.field
    def user_suggestions(self, info, offset: int = 0, limit: int = 10) -> Paged[auth_types.User]:
        current_user = info.context.request.user
        query = (
            auth_models.User.objects.select_related("profile")
            .filter(auth_models.User.is_visible_query(current_user))
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
