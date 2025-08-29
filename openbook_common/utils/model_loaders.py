import typing
from typing import Type

from django.apps import apps

if typing.TYPE_CHECKING:
    from feed_posts.models import FeedPost
    from openbook_appointments.models import Appointment
    from volunteering.models import VolunteeringOpportunityStatus
    from openbook_communities.models.completed_task import CompletedTask


def get_circle_model():
    return apps.get_model("openbook_circles.Circle")


def get_connection_model():
    return apps.get_model("openbook_connections.Connection")


def get_follow_model():
    return apps.get_model("openbook_follows.Follow")


def get_follow_request_model():
    return apps.get_model("openbook_follows.FollowRequest")


def get_post_model():
    return apps.get_model("openbook_posts.Post")


def get_poll_model():
    return apps.get_model("openbook_polls.Poll")


def get_choice_model():
    return apps.get_model("openbook_polls.Choice")


def get_top_post_model():
    return apps.get_model("openbook_posts.TopPost")


def get_trending_post_model():
    return apps.get_model("openbook_posts.TrendingPost")


def get_top_post_community_exclusion_model():
    return apps.get_model("openbook_posts.TopPostCommunityExclusion")


def get_profile_posts_community_exclusion_model():
    return apps.get_model("openbook_posts.ProfilePostsCommunityExclusion")


def get_post_media_model():
    return apps.get_model("openbook_posts.PostMedia")


def get_proxy_blacklist_domain_model():
    return apps.get_model("openbook_common.ProxyBlacklistedDomain")


def get_post_user_mention_model():
    return apps.get_model("openbook_posts.PostUserMention")


def get_comment_user_mention_model():
    return apps.get_model("comments.CommentUserMention")


def get_post_mute_model():
    return apps.get_model("openbook_posts.PostMute")


def get_comment_mute_model():
    return apps.get_model("comments.CommentMute")


def get_user_block_model():
    return apps.get_model("openbook_auth.UserBlock")


def get_list_model():
    return apps.get_model("openbook_lists.List")


def get_community_model():
    return apps.get_model("openbook_communities.Community")


def get_community_notifications_subscription_model():
    return apps.get_model("openbook_communities.CommunityNotificationsSubscription")


def get_community_invite_model():
    return apps.get_model("openbook_communities.CommunityInvite")


def get_community_pending_invite_model():
    return apps.get_model("openbook_communities.CommunityPendingInvite")


def get_community_log_model():
    return apps.get_model("openbook_communities.CommunityLog")


def get_comment_model():
    return apps.get_model("comments.Comment")


def get_post_reaction_model():
    return apps.get_model("openbook_posts.PostReaction")


def get_comment_reaction_model():
    return apps.get_model("comments.CommentReaction")


def get_emoji_model():
    return apps.get_model("openbook_common.Emoji")


def get_emoji_group_model():
    return apps.get_model("openbook_common.EmojiGroup")


def get_user_invite_model():
    return apps.get_model("openbook_invitations.UserInvite")


def get_badge_model():
    return apps.get_model("openbook_common.Badge")


def get_language_model():
    return apps.get_model("openbook_common.Language")


def get_hashtag_model():
    return apps.get_model("openbook_hashtags.Hashtag")


def get_category_model():
    return apps.get_model("openbook_categories.Category")


def get_community_membership_model():
    return apps.get_model("openbook_communities.CommunityMembership")


# deprecated - use novu specific Notifications class
def get_community_membership_approved_notification_model():
    return apps.get_model("openbook_notifications.CommunityMembershipApprovedNotification")


# deprecated - use novu specific Notifications class
def get_community_membership_request_notification_model():
    return apps.get_model("openbook_notifications.CommunityMembershipRequestNotification")


# deprecated - use novu specific Notifications class
def get_community_membership_revoked_notification_model():
    return apps.get_model("openbook_notifications.CommunityMembershipRevokedNotification")


# deprecated - use novu specific Notifications class
def get_community_invite_declined_notification_model():
    return apps.get_model("openbook_notifications.CommunityInviteDeclinedNotification")


# deprecated - use novu specific Notifications class
def get_community_admin_privileges_granted_notification_model():
    return apps.get_model("openbook_notifications.CommunityAdminPrivilegesGrantedNotification")


# deprecated - use novu specific Notifications class
def get_community_admin_privileges_revoked_notification_model():
    return apps.get_model("openbook_notifications.CommunityAdminPrivilegesRevokedNotification")


# deprecated - use novu specific Notifications class
def get_post_comment_notification_model():
    return apps.get_model("openbook_notifications.PostCommentNotification")


# deprecated - use novu specific Notifications class
def get_post_user_mention_notification_model():
    return apps.get_model("openbook_notifications.PostUserMentionNotification")


# deprecated - use novu specific Notifications class
def get_post_comment_user_mention_notification_model():
    return apps.get_model("openbook_notifications.PostCommentUserMentionNotification")


# deprecated - use novu specific Notifications class
def get_post_comment_reply_notification_model():
    return apps.get_model("openbook_notifications.PostCommentReplyNotification")


# deprecated - use novu specific Notifications class
def get_post_reaction_notification_model():
    return apps.get_model("openbook_notifications.PostReactionNotification")


# deprecated - use novu specific Notifications class
def get_post_comment_reaction_notification_model():
    return apps.get_model("openbook_notifications.PostCommentReactionNotification")


# deprecated - use novu specific Notifications class
def get_follow_notification_model():
    return apps.get_model("openbook_notifications.FollowNotification")


# deprecated - use novu specific Notifications class
def get_follow_request_notification_model():
    return apps.get_model("openbook_notifications.FollowRequestNotification")


# deprecated - use novu specific Notifications class
def get_follow_request_approved_notification_model():
    return apps.get_model("openbook_notifications.FollowRequestApprovedNotification")


# deprecated - use novu specific Notifications class
def get_connection_request_notification_model():
    return apps.get_model("openbook_notifications.ConnectionRequestNotification")


# deprecated - use novu specific Notifications class
def get_connection_confirmed_notification_model():
    return apps.get_model("openbook_notifications.ConnectionConfirmedNotification")


# deprecated - use novu specific Notifications class
def get_community_invite_notification_model():
    return apps.get_model("openbook_notifications.CommunityInviteNotification")


# deprecated - use novu specific Notifications class
def get_community_new_post_notification_model():
    return apps.get_model("openbook_notifications.CommunityNewPostNotification")


# deprecated - use novu specific Notifications class
def get_user_new_post_notification_model():
    return apps.get_model("openbook_notifications.UserNewPostNotification")


# deprecated - use novu specific Notifications class
def get_notification_model():
    return apps.get_model("openbook_notifications.Notification")


def get_device_model():
    return apps.get_model("openbook_devices.Device")


def get_user_model():
    return apps.get_model("openbook_auth.User")


def get_user_notifications_subscription_model():
    return apps.get_model("openbook_auth.UserNotificationsSubscription")


def get_moderated_object_model():
    return apps.get_model("openbook_moderation.ModeratedObject")


def get_moderation_report_model():
    return apps.get_model("openbook_moderation.ModerationReport")


def get_moderation_category_model():
    return apps.get_model("openbook_moderation.ModerationCategory")


def get_moderation_penalty_model():
    return apps.get_model("openbook_moderation.ModerationPenalty")


def get_skill_model():
    return apps.get_model("openbook_terms.Skill")


def get_topic_model():
    return apps.get_model("openbook_terms.Topic")


def get_sdg_model():
    return apps.get_model("openbook_terms.SDG")


def get_collaboration_tool_model():
    return apps.get_model("openbook_communities.CollaborationTool")


def get_task_model():
    return apps.get_model("openbook_communities.Task")


def get_external_link_model():
    return apps.get_model("openbook_communities.ExternalLink")


def get_onboarding_step_model():
    return apps.get_model("openbook_communities.OnboardingStep")


def get_insight_model():
    return apps.get_model("openbook_insights.Insight")


def get_quote_model():
    return apps.get_model("openbook_insights.Quote")


def get_quote_reaction_model():
    return apps.get_model("openbook_insights.QuoteReaction")


def get_recommendation_model():
    return apps.get_model("openbook_insights.Recommendation")


def get_recommendation_reaction_model():
    return apps.get_model("openbook_insights.RecommendationReaction")


def get_initiative_model():
    return apps.get_model("openbook_insights.Initiative")


def get_initiative_reaction_model():
    return apps.get_model("openbook_insights.InitiativeReaction")


def get_feed_post_model() -> Type["FeedPost"]:
    return apps.get_model("feed_posts.FeedPost")


def get_feed_post_reaction_model():
    return apps.get_model("feed_posts.FeedPostReaction")


def get_appointment_model() -> Type["Appointment"]:
    return apps.get_model("openbook_appointments.Appointment")


def get_volunteering_opportunity_status_model() -> Type["VolunteeringOpportunityStatus"]:
    return apps.get_model("volunteering.VolunteeringOpportunityStatus")


def get_completed_task_model() -> Type["CompletedTask"]:
    return apps.get_model("openbook_communities.completed_task.CompletedTask")
