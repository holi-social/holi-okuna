import json

from graphql import GraphQLError
from rest_framework.exceptions import ValidationError
from djangorestframework_camel_case.util import camelize

from openbook.graphql_errors import GraphQLErrorCodes

from strawberry.extensions import Extension


class GraphQLErrorExtension(Extension):
    @classmethod
    def resolve(self, _next, root, info, *args, **kwargs):
        try:
            return _next(root, info, *args, **kwargs)
        except ValidationError as error:
            raise GraphQLError(
                "Bad user input",
                extensions={
                    "code": GraphQLErrorCodes.BAD_USER_INPUT,
                    "errors": json.dumps(camelize(error.get_full_details())),
                },
            )
