import json

from graphql import GraphQLError
from rest_framework.exceptions import ValidationError

from openbook.graphql_errors import GraphQLErrorCodes


def graphql_error_context_middleware(next, root, info, **args):
    try:
        return next(root, info, **args)
    except ValidationError as error:
        raise GraphQLError(
            "Bad user input",
            extensions={
                "code": GraphQLErrorCodes.BAD_USER_INPUT,
                "errors": json.dumps(error.get_full_details()),
            },
        )
