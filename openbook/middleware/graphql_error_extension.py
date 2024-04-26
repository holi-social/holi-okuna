import json

from graphql import GraphQLError
from rest_framework.exceptions import ValidationError
from django.core.exceptions import ValidationError as CoreValidationError, ObjectDoesNotExist, PermissionDenied
from djangorestframework_camel_case.util import camelize
from strawberry.utils.await_maybe import await_maybe

from openbook.graphql_errors import GraphQLErrorCodes

from strawberry.extensions import Extension


class GraphQLErrorExtension(Extension):
    @classmethod
    async def resolve(self, _next, root, info, *args, **kwargs):
        try:
            return await await_maybe(_next(root, info, *args, **kwargs))
        except ValidationError as error:
            raise GraphQLError(
                "Bad user input",
                extensions={
                    "code": GraphQLErrorCodes.BAD_USER_INPUT,
                    "errors": json.dumps(camelize(error.get_full_details())),
                },
            )
        except CoreValidationError as error:
            validationError = ValidationError(error.message_dict)
            raise GraphQLError(
                "Bad user input",
                extensions={
                    "code": GraphQLErrorCodes.BAD_USER_INPUT,
                    "errors": json.dumps(camelize(validationError.get_full_details())),
                },
            )
        except ObjectDoesNotExist:
            raise GraphQLError("Object not found", extensions={"code": GraphQLErrorCodes.NOT_FOUND})
        except PermissionDenied:
            raise GraphQLError("Forbidden", extensions={"code": GraphQLErrorCodes.FORBIDDEN})
