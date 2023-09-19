import uuid
from typing import Optional

import strawberry
from asgiref.sync import sync_to_async
from graphql import GraphQLError

from openbook_auth.utils import verify_authorized_user
from openbook.graphql_errors import GraphQLErrorCodes
from openbook_common.schema.types import Result
from openbook_moderation.enums import ContentType


@strawberry.type
class Mutation:
    @strawberry.mutation
    @sync_to_async
    def report_content(
        self,
        info,
        object_id: uuid.UUID,
        content_type: ContentType,
        description: Optional[str] = None,
    ) -> Result:
        current_user = verify_authorized_user(info)

        # hardcoded category_id to block user content. Needs to be imported via fixture!
        category_id = uuid.UUID("00000000-0000-0000-0000-000000000001")
        match content_type:
            case ContentType.POST:
                current_user.report_post_with_id(object_id, category_id, description)
            case ContentType.POST_COMMENT:
                current_user.report_comment_with_id(object_id, category_id, description)
            case ContentType.USER:
                current_user.report_user_with_username(str(object_id), category_id, description)
            case ContentType.SPACE:
                current_user.report_community_with_id(object_id, category_id, description)
            case _:
                raise GraphQLError(
                    f"Unknown ContentType {content_type.value}",
                    extensions={"code": GraphQLErrorCodes.FORBIDDEN},
                )

        return Result(success=True)
