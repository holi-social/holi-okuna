import uuid

from django.apps import apps as django_apps
from django.contrib.admin.utils import NestedObjects
from django.contrib.auth import validators
from django.contrib.contenttypes.models import ContentType
from django.db import connections, migrations, models, transaction

""" List of relations with openboook_auth_user table obtained with sql:
SELECT la.attrelid::regclass AS referencing_table,
       la.attname AS referencing_column
FROM pg_constraint AS c
   JOIN pg_index AS i
      ON i.indexrelid = c.conindid
   JOIN pg_attribute AS la
      ON la.attrelid = c.conrelid
         AND la.attnum = c.conkey[1]
   JOIN pg_attribute AS ra
      ON ra.attrelid = c.confrelid
         AND ra.attnum = c.confkey[1]
WHERE c.confrelid = 'openbook_auth_user'::regclass
  AND c.contype = 'f'
  AND ra.attname = 'id'
  AND cardinality(c.confkey) = 1;
"""
tables = [
    ("openbook_communities_communitylog", "target_user_id"),
    ("openbook_communities_communitylog", "source_user_id"),
    ("openbook_moderation_moderatedobjectlog", "actor_id"),
    ("openbook_notifications_communitymembershipapprovednotification", "approved_user_id"),
    ("openbook_notifications_connectionacceptednotification", "connected_user_id"),
    ("openbook_notifications_connectionrequestnotification", "connection_requester_id"),
    ("openbook_notifications_connectionconfirmednotification", "connection_confirmator_id"),
    ("openbook_communities_community_banned_users", "user_id"),
    ("openbook_communities_community_starrers", "user_id"),
    ("openbook_auth_user_groups", "user_id"),
    ("openbook_auth_user_user_permissions", "user_id"),
    ("authtoken_token", "user_id"),
    ("openbook_auth_userblock", "blocked_user_id"),
    ("openbook_circles_circle", "creator_id"),
    ("openbook_communities_communityinvite", "invited_user_id"),
    ("openbook_communities_communitymembership", "user_id"),
    ("openbook_communities_communitymembershiprequest", "user_id"),
    ("openbook_communities_communitynotificationssubscription", "subscriber_id"),
    ("openbook_connections_connection", "user_id"),
    ("openbook_categories_category", "creator_id"),
    ("openbook_communities_collaborationtool", "creator_id"),
    ("openbook_communities_community", "creator_id"),
    ("openbook_communities_communityinvite", "creator_id"),
    ("openbook_communities_task", "creator_id"),
    ("openbook_insights_insight", "creator_id"),
    ("openbook_devices_device", "owner_id"),
    ("openbook_follows_follow", "followed_user_id"),
    ("openbook_notifications_follownotification", "follower_id"),
    ("openbook_follows_follow", "user_id"),
    ("openbook_invitations_userinvite", "invited_by_id"),
    ("openbook_lists_list", "creator_id"),
    ("django_admin_log", "user_id"),
    ("openbook_moderation_moderationpenalty", "user_id"),
    ("openbook_moderation_moderationreport", "reporter_id"),
    ("openbook_notifications_notification", "owner_id"),
    ("openbook_auth_usernotificationssettings", "user_id"),
    ("openbook_auth_usernotificationssubscription", "user_id"),
    ("openbook_posts_postcommentusermention", "user_id"),
    ("openbook_posts_postcommentmute", "muter_id"),
    ("openbook_posts_postcommentreaction", "reactor_id"),
    ("openbook_posts_postusermention", "user_id"),
    ("openbook_posts_postmute", "muter_id"),
    ("openbook_posts_postreaction", "reactor_id"),
    ("openbook_posts_post", "creator_id"),
    ("openbook_posts_postcomment", "commenter_id"),
    ("openbook_auth_userprofile", "user_id"),
    ("openbook_posts_profilepostscommunityexclusion", "user_id"),
    ("openbook_follows_followrequest", "target_user_id"),
    ("openbook_follows_followrequest", "creator_id"),
    ("openbook_connections_connection", "target_user_id"),
    ("openbook_posts_toppostcommunityexclusion", "user_id"),
    ("openbook_auth_userblock", "blocker_id"),
    ("openbook_auth_usernotificationssubscription", "subscriber_id"),
    ("openbook_invitations_userinvite", "created_user_id"),
]


def update_auth_user_id(apps, schema_editor):
    User = apps.get_model("openbook_auth", "User")
    cursor = connections["default"].cursor()

    for obj in User.objects.all():
        old_id = obj.id
        obj.id = obj.uuid
        obj.save()

        for table_name, field_name in tables:
            cursor.execute(f"UPDATE {table_name} SET {field_name}='{obj.id}' WHERE {field_name}='{old_id}'")

        User.objects.filter(id=old_id).first().delete()


class Migration(migrations.Migration):

    dependencies = [
        ("openbook_auth", "0008_alter_user_id"),
    ]

    operations = [
        migrations.AlterField(
            model_name="user",
            name="email",
            field=models.EmailField(max_length=254, verbose_name="email address"),
        ),
        migrations.AlterField(
            model_name="user",
            name="username",
            field=models.CharField(
                error_messages={"unique": "A user with that username already exists."},
                help_text="Required. 36 characters or fewer. Letters, digits and _ only.",
                max_length=36,
                validators=[validators.UnicodeUsernameValidator()],
                verbose_name="username",
            ),
        ),
        migrations.AlterField(
            model_name="user",
            name="uuid",
            field=models.UUIDField(default=uuid.uuid4, editable=False),
        ),
        migrations.RunPython(update_auth_user_id),
    ]
