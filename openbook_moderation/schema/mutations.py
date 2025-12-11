import uuid
from typing import Optional, TYPE_CHECKING

import strawberry
from asgiref.sync import sync_to_async
from graphql import GraphQLError

from openbook.settings import MODERATION_REPORT_URL, ENVIRONMENT_ID
from openbook_auth.utils import verify_authorized_user
from openbook.graphql_errors import GraphQLErrorCodes
from openbook_common.helpers import send_alert_to_channel
from openbook_common.schema.types import Result
from openbook_moderation.enums import ContentType

if TYPE_CHECKING:
    from openbook_auth.models import User


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
        current_user: "User" = verify_authorized_user(info)

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
            case ContentType.FEED_POST:
                current_user.report_feed_post_by_id(object_id, category_id, description)
            case ContentType.SPACE_TASK:
                current_user.report_space_task_by_id(object_id, category_id, description)
            case ContentType.SPACE_APPOINTMENT:
                current_user.report_appointment_by_id(object_id, category_id, description)
            case _:
                raise GraphQLError(
                    f"Unknown ContentType {content_type.value}",
                    extensions={"code": GraphQLErrorCodes.FORBIDDEN},
                )
        send_alert_to_channel(
            f"*{ENVIRONMENT_ID}* moderation report for {content_type.value} with ID {object_id} by user {current_user.username}",
            MODERATION_REPORT_URL,
        )

        return Result(success=True)
