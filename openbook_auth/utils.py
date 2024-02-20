from graphql import GraphQLError

from openbook.graphql_errors import GraphQLErrorCodes


def normalize_spaces(input_string):
    return " ".join(input_string.strip().split())


def verify_authorized_user(info):
    current_user = info.context.request.user
    if not current_user or current_user.is_anonymous:
        raise GraphQLError("Unauthorized", extensions={"code": GraphQLErrorCodes.UNAUTHORIZED})
    return current_user


def check_max_limit(maximum: int, offset: int, limit: int):
    if offset >= maximum:
        raise GraphQLError("Forbidden", extensions={"code": GraphQLErrorCodes.FORBIDDEN})

    # we return a new limit that ensures: offset + new limit <= maximum
    # eg. maximum=20, offset=15, limit=10, then the new limit is 5.
    return min(maximum, offset + limit) - offset
