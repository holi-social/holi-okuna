from dataclasses import dataclass
from typing import Dict


@dataclass
class Event:
    name: str
    properties: Dict[str, str]
    event_version__major: int
    event_version__minor: int
    event_version__patch: int


# class EventEnum(Enum):
#     USER_CREATED = EventPayload("user_created", {}, 1, 0, 0)
#     USER_UPDATED = EventPayload("user_updated", {}, 1, 0, 0)
#     USER_DELETED = EventPayload("user_deleted", {}, 1, 0, 0)
#
#     SPACE_CREATED = EventPayload("space_created", {}, 1, 0, 0)
#     SPACE_UPDATED = EventPayload("space_updated", {}, 1, 0, 0)
#     SPACE_DELETED = EventPayload("space_deleted", {}, 1, 0, 0)
#
#     SPACE_POST_CREATED = EventPayload("space_post_created", {}, 1, 0, 0)
#     SPACE_POST_UPDATED = EventPayload("space_post_updated", {}, 1, 0, 0)
#     SPACE_POST_DELETED = EventPayload("space_post_deleted", {}, 1, 0, 0)
#
#     SPACE_POST_COMMENT_CREATED = EventPayload("space_post_comment_created", {}, 1, 0, 0)
#     SPACE_POST_COMMENT_UPDATED = EventPayload("space_post_comment_updated", {}, 1, 0, 0)
#     SPACE_POST_COMMENT_DELETED = EventPayload("space_post_comment_deleted", {}, 1, 0, 0)
#
#     POST_CREATED = EventPayload("post_created", {}, 1, 0, 0)
#     POST_UPDATED = EventPayload("post_updated", {}, 1, 0, 0)
#     POST_DELETED = EventPayload("post_deleted", {}, 1, 0, 0)
#
#     POST_COMMENT_CREATED = EventPayload("post_comment_created", {}, 1, 0, 0)
#     POST_COMMENT_UPDATED = EventPayload("post_comment_updated", {}, 1, 0, 0)
#     POST_COMMENT_DELETED = EventPayload("post_comment_deleted", {}, 1, 0, 0)
#
#     FEED_POST_CREATED = EventPayload("feed_post_created", {}, 1, 0, 0)
#     FEED_POST_UPDATED = EventPayload("feed_post_updated", {}, 1, 0, 0)
#     FEED_POST_DELETED = EventPayload("feed_post_deleted", {}, 1, 0, 0)
#
#     FEED_POST_COMMENT_CREATED = EventPayload("feed_post_comment_created", {}, 1, 0, 0)
#     FEED_POST_COMMENT_UPDATED = EventPayload("feed_post_comment_updated", {}, 1, 0, 0)
#     FEED_POST_COMMENT_DELETED = EventPayload("feed_post_comment_deleted", {}, 1, 0, 0)
#
#     INSIGHT_DISCUSSION_COMMENT_CREATED = EventPayload("insight_discussion_comment_created", {}, 1, 0, 0)
#     INSIGHT_DISCUSSION_COMMENT_UPDATED = EventPayload("insight_discussion_comment_updated", {}, 1, 0, 0)
#     INSIGHT_DISCUSSION_COMMENT_DELETED = EventPayload("insight_discussion_comment_deleted", {}, 1, 0, 0)
#
#     APPOINTMENT_CREATED = EventPayload("appointment_created", {}, 1, 0, 0)
#     APPOINTMENT_UPDATED = EventPayload("appointment_updated", {}, 1, 0, 0)
#     APPOINTMENT_DELETED = EventPayload("appointment_deleted", {}, 1, 0, 0)
#
#     SPACE_TASK_CREATED = EventPayload("space_task_created", {}, 1, 0, 0)
#     SPACE_TASK_UPDATED = EventPayload("space_task_updated", {}, 1, 0, 0)
#     SPACE_TASK_DELETED = EventPayload("space_task_deleted", {}, 1, 0, 0)
