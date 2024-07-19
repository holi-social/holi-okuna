from enum import Enum


class Event(Enum):
    USER_CREATED = "user_created"
    USER_UPDATED = "user_updated"
    USER_DELETED = "user_deleted"

    COMMUNITY_CREATED = "community_created"
    COMMUNITY_UPDATED = "community_updated"
    COMMUNITY_DELETED = "community_deleted"

    COMMUNITY_POST_CREATED = "community_post_created"
    COMMUNITY_POST_UPDATED = "community_post_updated"
    COMMUNITY_POST_DELETED = "community_post_deleted"

    COMMUNITY_POST_COMMENT_CREATED = "community_post_comment_created"
    COMMUNITY_POST_COMMENT_UPDATED = "community_post_comment_updated"
    COMMUNITY_POST_COMMENT_DELETED = "community_post_comment_deleted"

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

    COMMUNITY_TASK_CREATED = "community_task_created"
    COMMUNITY_TASK_UPDATED = "community_task_updated"
    COMMUNITY_TASK_DELETED = "community_task_deleted"
