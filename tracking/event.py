from enum import Enum


class Event(Enum):
    USER_CREATED = "user_created"
    USER_UPDATED = "user_updated"
    USER_DELETED = "user_deleted"

    SPACE_CREATED = "space_created"
    SPACE_UPDATED = "space_updated"
    SPACE_DELETED = "space_deleted"

    SPACE_POST_CREATED = "space_post_created"
    SPACE_POST_UPDATED = "space_post_updated"
    SPACE_POST_DELETED = "space_post_deleted"

    SPACE_POST_COMMENT_CREATED = "space_post_comment_created"
    SPACE_POST_COMMENT_UPDATED = "space_post_comment_updated"
    SPACE_POST_COMMENT_DELETED = "space_post_comment_deleted"

    POST_CREATED = "post_created"
    POST_UPDATED = "post_updated"
    POST_DELETED = "post_deleted"

    POST_COMMENT_CREATED = "post_comment_created"
    POST_COMMENT_UPDATED = "post_comment_updated"
    POST_COMMENT_DELETED = "post_comment_deleted"

    FEED_POST_CREATED = "feed_post_created"
    FEED_POST_UPDATED = "feed_post_updated"
    FEED_POST_DELETED = "feed_post_deleted"

    FEED_POST_COMMENT_CREATED = "feed_post_comment_created"
    FEED_POST_COMMENT_UPDATED = "feed_post_comment_updated"
    FEED_POST_COMMENT_DELETED = "feed_post_comment_deleted"

    INSIGHT_DISCUSSION_COMMENT_CREATED = "insight_discussion_comment_created"
    INSIGHT_DISCUSSION_COMMENT_UPDATED = "insight_discussion_comment_updated"
    INSIGHT_DISCUSSION_COMMENT_DELETED = "insight_discussion_comment_deleted"

    APPOINTMENT_CREATED = "appointment_created"
    APPOINTMENT_UPDATED = "appointment_updated"
    APPOINTMENT_DELETED = "appointment_deleted"

    SPACE_TASK_CREATED = "space_task_created"
    SPACE_TASK_UPDATED = "space_task_updated"
    SPACE_TASK_DELETED = "space_task_deleted"
