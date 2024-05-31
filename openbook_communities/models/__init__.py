# ruff: noqa
import uuid
from enum import Enum
from hashlib import sha256
from typing import List, Optional

import strawberry
from django.conf import settings
from django.contrib.contenttypes.fields import GenericRelation
from django.contrib.gis.db import models
from django.contrib.gis.db.models import Count
from django.contrib.gis.db.models import Q
from django.core.files.storage import default_storage
from django.db import transaction
from django.db.models import QuerySet
from django.utils import timezone
from django.utils.translation import gettext_lazy as _
from imagekit.models import ProcessedImageField
from pilkit.processors import ResizeToFill, ResizeToFit

from openbook.settings import COLOR_ATTR_MAX_LENGTH
from openbook_auth.models import User
from openbook_common.enums import VisibilityType
from openbook_common.helpers import ExifRotate, generate_blurhash, PrefixedQ
from openbook_common.models import ModelWithUUID
from openbook_common.utils.helpers import delete_file_field, extract_and_capitalize_domain_name
from openbook_common.utils.model_loaders import (
    get_community_invite_model,
    get_community_pending_invite_model,
    get_community_log_model,
    get_category_model,
    get_sdg_model,
    get_topic_model,
    get_skill_model,
    get_community_notifications_subscription_model,
    get_community_new_post_notification_model,
    get_community_invite_notification_model,
    get_onboarding_step_model,
)
from openbook_common.validators import hex_color_validator
from openbook_communities.helpers import (
    create_community_name_from_title_and_hash,
    upload_to_community_avatar_directory,
    upload_to_community_cover_directory,
    upload_to_community_task_thumbnail_directory,
)
from openbook_communities.queries import (
    make_search_communities_query_for_user,
    make_search_joined_communities_query_for_user,
    make_get_joined_communities_query_for_user,
)
from openbook_moderation.models import ModeratedObject
from openbook_notifications.api import NotificationApi
from openbook_posts.models import Post
from openbook_terms.models import SDG, Topic, Skill

community_image_storage = default_storage
community_task_image_storage = default_storage


@strawberry.enum
class SpaceUserConnectionType(Enum):
    FOLLOWER = "FOLLOWER"
    MEMBERSHIP_REQUESTOR = "MEMBERSHIP_REQUESTOR"
    MEMBERSHIP_INVITEE = "MEMBERSHIP_INVITEE"
    MEMBER = "MEMBER"
    CREATOR = "CREATOR"
    ADMINISTRATOR = "ADMINISTRATOR"


class Community(ModelWithUUID):
    moderated_object = GenericRelation(ModeratedObject, related_query_name="communities")
    creator = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        related_name="created_communities",
        null=True,
        blank=False,
    )
    name = models.SlugField(
        _("name"),
        max_length=settings.COMMUNITY_NAME_MAX_LENGTH,
        blank=False,
        null=False,
        unique=True,
    )
    title = models.CharField(
        _("title"),
        max_length=settings.COMMUNITY_TITLE_MAX_LENGTH,
        blank=False,
        null=False,
    )
    description = models.TextField(
        _("description"),
        blank=False,
        null=True,
    )
    rules = models.TextField(
        _("rules"),
        max_length=settings.COMMUNITY_RULES_MAX_LENGTH,
        blank=True,
        null=True,
    )
    avatar = ProcessedImageField(
        storage=community_image_storage,
        verbose_name=_("avatar"),
        blank=True,
        null=True,
        processors=[
            ExifRotate(),
            ResizeToFill(
                settings.PROFILE_IMAGE_MAX_DIMENSION,
                settings.PROFILE_IMAGE_MAX_DIMENSION,
                upscale=False,
            ),
        ],
        upload_to=upload_to_community_avatar_directory,
        max_length=settings.IMAGE_URL_MAX_LENGTH,
        default=None,
    )
    avatar_blurhash = models.CharField(max_length=50, blank=True, null=True)
    cover = ProcessedImageField(
        storage=community_image_storage,
        verbose_name=_("cover"),
        blank=False,
        null=True,
        upload_to=upload_to_community_cover_directory,
        processors=[
            ExifRotate(),
            ResizeToFit(
                width=settings.CONTENT_IMAGE_MAX_DIMENSION,
                height=settings.CONTENT_IMAGE_MAX_DIMENSION,
                upscale=False,
            ),
        ],
        max_length=settings.IMAGE_URL_MAX_LENGTH,
    )
    cover_blurhash = models.CharField(max_length=50, blank=True, null=True)
    created = models.DateTimeField(default=timezone.now, editable=True)
    starrers = models.ManyToManyField(User, related_name="favorite_communities", blank=True)
    banned_users = models.ManyToManyField(User, related_name="banned_of_communities", blank=True)
    COMMUNITY_TYPE_PRIVATE = "T"
    COMMUNITY_TYPE_PUBLIC = "P"
    COMMUNITY_TYPES = (
        (COMMUNITY_TYPE_PUBLIC, "Public"),
        (COMMUNITY_TYPE_PRIVATE, "Private"),
    )
    DEFAULT_AVATAR_COLORS = settings.DEFAULT_AVATAR_COLORS

    type = models.CharField(
        editable=False,
        blank=False,
        null=False,
        choices=COMMUNITY_TYPES,
        default="P",
        max_length=2,
    )
    color = models.CharField(
        _("color"),
        max_length=COLOR_ATTR_MAX_LENGTH,
        blank=True,
        null=True,
        validators=[hex_color_validator],
    )
    user_adjective = models.CharField(
        _("user adjective"),
        max_length=settings.COMMUNITY_USER_ADJECTIVE_MAX_LENGTH,
        blank=True,
        null=True,
    )
    users_adjective = models.CharField(
        _("users adjective"),
        max_length=settings.COMMUNITY_USERS_ADJECTIVE_MAX_LENGTH,
        blank=True,
        null=True,
    )
    invites_enabled = models.BooleanField(_("invites enabled"), default=True)
    # This only happens if the community was reported and found with critical severity content
    is_deleted = models.BooleanField(
        _("is deleted"),
        default=False,
    )
    location = models.CharField(
        max_length=settings.COMMUNITY_LOCATION_MAX_LENGTH,
        blank=True,
        null=True,
        db_index=True,
    )
    topics = models.ManyToManyField(Topic, related_name="communities", blank=False, db_index=True)
    sdgs = models.ManyToManyField(SDG, related_name="communities", blank=True, db_index=True)
    geolocation = models.PointField(blank=True, null=True, spatial_index=True)
    contact_description = models.CharField(
        max_length=settings.COMMUNITY_CONTACT_DESCRIPTION_MAX_LENGTH,
        blank=True,
        null=True,
    )
    contact_email = models.EmailField(
        _("contact email"),
        blank=True,
        null=True,
    )
    contact_phone = models.CharField(
        max_length=settings.COMMUNITY_CONTACT_PHONE_MAX_LENGTH,
        blank=True,
        null=True,
    )

    #  Backwards relations
    memberships: QuerySet["CommunityMembership"]

    class Meta:
        verbose_name_plural = "communities"

    @property
    def avatar_default_color(self):
        color_count = len(Community.DEFAULT_AVATAR_COLORS) - 1
        color = sum(list(self.title.encode("utf8"))) % color_count
        return Community.DEFAULT_AVATAR_COLORS[color]

    @classmethod
    def is_user_with_username_invited_to_community_with_name(cls, username, community_name):
        CommunityInvite = get_community_invite_model()
        return CommunityInvite.is_user_with_username_invited_to_community_with_name(
            username=username, community_name=community_name
        )

    @classmethod
    def is_user_with_username_subscribed_to_notifications_for_community_with_name(cls, username, community_name):
        CommunityNotificationsSubscription = get_community_notifications_subscription_model()
        return CommunityNotificationsSubscription.are_new_post_notifications_enabled_for_user_with_username_and_community_with_name(
            username=username, community_name=community_name
        )

    @classmethod
    def is_user_with_username_member_of_community_with_name(cls, username, community_name):
        return cls.objects.filter(name=community_name, memberships__user__username=username).exists()

    @classmethod
    def is_user_with_username_administrator_of_community_with_name(cls, username, community_name):
        return cls.objects.filter(
            name=community_name,
            memberships__user__username=username,
            memberships__is_administrator=True,
        ).exists()

    @classmethod
    def is_user_with_username_moderator_of_community_with_name(cls, username, community_name):
        return cls.objects.filter(
            name=community_name,
            memberships__user__username=username,
            memberships__is_moderator=True,
        ).exists()

    @classmethod
    def is_user_with_username_banned_from_community_with_name(cls, username, community_name):
        return cls.objects.filter(name=community_name, banned_users__username=username).exists()

    @classmethod
    def is_community_with_name_invites_enabled(cls, community_name):
        return cls.objects.filter(name=community_name, invites_enabled=True).exists()

    @classmethod
    def is_community_with_name_private(cls, community_name):
        return cls.objects.filter(name=community_name, type="T").exists()

    @classmethod
    def community_with_name_exists(cls, community_name):
        query = Q(name=community_name, is_deleted=False)
        return cls.objects.filter(query).exists()

    @classmethod
    def community_with_id_exists(cls, community_id):
        query = Q(id=community_id, is_deleted=False)
        return cls.objects.filter(query).exists()

    @classmethod
    def get_community_with_name_for_user_with_id(cls, community_name, user_id):
        query = Q(name=community_name, is_deleted=False)
        query.add(~Q(banned_users__id=user_id), Q.AND)
        return cls.objects.get(query)

    @classmethod
    def search_communities_with_query_for_user(cls, query, user, excluded_from_profile_posts=True):
        query = make_search_communities_query_for_user(
            query=query,
            user=user,
            excluded_from_profile_posts=excluded_from_profile_posts,
        )
        return cls.objects.filter(query)

    @classmethod
    def search_joined_communities_with_query_for_user(cls, query, user, excluded_from_profile_posts=True):
        query = make_search_joined_communities_query_for_user(
            query=query,
            user=user,
            excluded_from_profile_posts=excluded_from_profile_posts,
        )
        return cls.objects.filter(query)

    @classmethod
    def get_joined_communities_for_user(cls, user, excluded_from_profile_posts=True):
        query = make_get_joined_communities_query_for_user(
            user=user, excluded_from_profile_posts=excluded_from_profile_posts
        )
        return cls.objects.filter(query)

    @classmethod
    def get_new_user_suggested_communities(cls):
        community_ids = [
            uuid.UUID(community_id) for community_id in settings.NEW_USER_SUGGESTED_COMMUNITIES.split(",")
        ]
        return cls.objects.filter(id__in=community_ids, type=cls.COMMUNITY_TYPE_PUBLIC)

    @classmethod
    def get_trending_communities_for_user_with_id(cls, user_id, category_name=None):
        trending_communities_query = cls._make_trending_communities_query(category_name=category_name)
        trending_communities_query.add(~Q(banned_users__id=user_id), Q.AND)
        return cls._get_trending_communities_with_query(query=trending_communities_query)

    @classmethod
    def get_trending_communities(cls, category_name=None):
        trending_communities_query = cls._make_trending_communities_query(category_name=category_name)
        return cls._get_trending_communities_with_query(query=trending_communities_query)

    @classmethod
    def _get_trending_communities_with_query(cls, query):
        return cls.objects.annotate(Count("memberships")).filter(query).order_by("-memberships__count", "-created")

    @classmethod
    def _make_trending_communities_query(cls, category_name=None):
        trending_communities_query = Q(type=cls.COMMUNITY_TYPE_PUBLIC, is_deleted=False)

        if category_name:
            trending_communities_query.add(Q(categories__name=category_name), Q.AND)

        return trending_communities_query

    @classmethod
    def create_community(
        cls,
        title,
        creator,
        color=None,
        type=COMMUNITY_TYPE_PUBLIC,
        user_adjective=None,
        users_adjective=None,
        avatar=None,
        cover=None,
        description=None,
        rules=None,
        categories_names=None,
        invites_enabled=None,
        location=None,
        topic_ids=None,
    ):
        # If it's a private community and no invites_enabled
        if type == Community.COMMUNITY_TYPE_PRIVATE and invites_enabled is None:
            invites_enabled = False
        else:
            # The default for this field is not working when passed None?
            invites_enabled = True

        community = cls.objects.create(
            title=title,
            creator=creator,
            avatar=avatar,
            avatar_blurhash=generate_blurhash(avatar),
            cover=cover,
            cover_blurhash=generate_blurhash(cover),
            color=color,
            user_adjective=user_adjective,
            users_adjective=users_adjective,
            description=description,
            type=type,
            rules=rules,
            invites_enabled=invites_enabled,
            location=location,
        )

        CommunityMembership.create_membership(
            user=creator, is_administrator=True, is_moderator=False, community=community
        )

        if categories_names:
            community.set_categories_with_names(categories_names=categories_names)
        if topic_ids:
            community.set_topics_with_ids(topic_ids=topic_ids)

        community.save()
        return community

    @classmethod
    def is_name_taken(cls, name):
        return cls.objects.filter(name__iexact=name).exists()

    EXCLUDE_COMMUNITY_ADMINISTRATORS_KEYWORD = "administrators"
    EXCLUDE_COMMUNITY_MODERATORS_KEYWORD = "moderators"

    @classmethod
    def get_community_with_name_members(cls, community_name, members_max_id=None, exclude_keywords=None):
        community_members_query = Q(communities_memberships__community__name=community_name)

        if members_max_id:
            community_members_query.add(Q(id__lt=members_max_id), Q.AND)

        if exclude_keywords:
            community_members_query.add(
                cls._get_exclude_members_query_for_keywords(exclude_keywords=exclude_keywords),
                Q.AND,
            )

        return User.objects.filter(community_members_query)

    @classmethod
    def search_community_with_name_members(cls, community_name, query, exclude_keywords=None):
        db_query = Q(communities_memberships__community__name=community_name)

        community_members_query = Q(communities_memberships__user__username__icontains=query)
        community_members_query.add(Q(communities_memberships__user__profile__name__icontains=query), Q.OR)

        db_query.add(community_members_query, Q.AND)

        if exclude_keywords:
            db_query.add(
                cls._get_exclude_members_query_for_keywords(exclude_keywords=exclude_keywords),
                Q.AND,
            )

        return User.objects.filter(db_query)

    @classmethod
    def _get_exclude_members_query_for_keywords(cls, exclude_keywords):
        query = Q()

        if cls.EXCLUDE_COMMUNITY_ADMINISTRATORS_KEYWORD in exclude_keywords:
            query.add(Q(communities_memberships__is_administrator=False), Q.AND)

        if cls.EXCLUDE_COMMUNITY_MODERATORS_KEYWORD in exclude_keywords:
            query.add(Q(communities_memberships__is_moderator=False), Q.AND)

        return query

    @classmethod
    def get_community_with_name_administrators(cls, community_name, administrators_max_id=None):
        community_administrators_query = Q(
            communities_memberships__community__name=community_name,
            communities_memberships__is_administrator=True,
        )

        if administrators_max_id:
            community_administrators_query.add(Q(communities_memberships__user__id__lt=administrators_max_id), Q.AND)

        return User.objects.filter(community_administrators_query)

    @classmethod
    def search_community_with_name_administrators(cls, community_name, query):
        db_query = Q(
            communities_memberships__community__name=community_name,
            communities_memberships__is_administrator=True,
        )

        community_members_query = Q(communities_memberships__user__username__icontains=query)
        community_members_query.add(Q(communities_memberships__user__profile__name__icontains=query), Q.OR)

        db_query.add(community_members_query, Q.AND)

        return User.objects.filter(db_query)

    @classmethod
    def get_community_with_name_moderators(cls, community_name, moderators_max_id=None):
        community_moderators_query = Q(
            communities_memberships__community__name=community_name,
            communities_memberships__is_moderator=True,
        )

        if moderators_max_id:
            community_moderators_query.add(Q(communities_memberships__user__id__lt=moderators_max_id), Q.AND)

        return User.objects.filter(community_moderators_query)

    @classmethod
    def search_community_with_name_moderators(cls, community_name, query):
        db_query = Q(
            communities_memberships__community__name=community_name,
            communities_memberships__is_moderator=True,
        )

        community_members_query = Q(communities_memberships__user__username__icontains=query)
        community_members_query.add(Q(communities_memberships__user__profile__name__icontains=query), Q.OR)

        db_query.add(community_members_query, Q.AND)

        return User.objects.filter(db_query)

    @classmethod
    def get_community_with_name_banned_users(cls, community_name, users_max_id):
        community = Community.objects.get(name=community_name)
        community_members_query = Q()

        if users_max_id:
            community_members_query.add(Q(id__lt=users_max_id), Q.AND)

        return community.banned_users.filter(community_members_query)

    @classmethod
    def search_community_with_name_banned_users(cls, community_name, query):
        community = Community.objects.get(name=community_name)
        community_banned_users_query = Q(username__icontains=query)
        community_banned_users_query.add(Q(profile__name__icontains=query), Q.OR)
        return community.banned_users.filter(community_banned_users_query)

    @property
    def members_count(self):
        return self.memberships.all().count()

    def get_staff_members(self):
        staff_members_query = Q(communities_memberships__community_id=self.pk)
        staff_members_query.add(
            Q(communities_memberships__is_administrator=True) | Q(communities_memberships__is_moderator=True),
            Q.AND,
        )
        return User.objects.filter(staff_members_query)

    def get_staff_and_subscribers(self):
        # covers all moderators because new joiners are subscribed automatically
        # also includes requestors that have pending join requests
        # admins aren't technically subscribing to a community, so they need to be queried
        return User.objects.filter(
            Q(community_notifications_subscriptions__community_id=self.pk)
            | Q(communities_memberships__community_id=self.pk, communities_memberships__is_administrator=True)
        ).distinct()

    def is_private(self):
        return self.type == self.COMMUNITY_TYPE_PRIVATE

    def update(
        self,
        title=None,
        description=None,
        color=None,
        type=None,
        user_adjective=None,
        users_adjective=None,
        rules=None,
        categories_names=None,
        invites_enabled=None,
        topic_ids=None,
        sdg_ids=None,
        cover=None,
        remove_cover=False,
        avatar=None,
        remove_avatar=False,
        location=None,
        geolocation=None,
        contact_description=None,
        contact_email=None,
        contact_phone=None,
        onboarding_steps=None,
    ):
        if title:
            self.title = title

        if type:
            self.type = type

        if color:
            self.color = color

        if description is not None:
            self.description = description

        if rules is not None:
            self.rules = rules

        if user_adjective is not None:
            self.user_adjective = user_adjective

        if users_adjective is not None:
            self.users_adjective = users_adjective

        if invites_enabled is not None:
            self.invites_enabled = invites_enabled

        if categories_names is not None:
            self.set_categories_with_names(categories_names=categories_names)

        if topic_ids is not None:
            self.set_topics_with_ids(topic_ids=topic_ids)

        if remove_cover:
            self._delete_cover()
        elif cover:
            self._update_cover(cover, save=False)

        if remove_avatar:
            self._delete_avatar()
        elif avatar:
            self._update_avatar(avatar, save=False)

        if sdg_ids is not None:
            self.set_sdgs_with_ids(sdg_ids=sdg_ids)

        if location:
            self.location = location

        if geolocation is not None:
            self.geolocation = geolocation

        if contact_description is not None:
            self.contact_description = contact_description

        if contact_email is not None:
            self.contact_email = contact_email

        if contact_phone is not None:
            self.contact_phone = contact_phone

        if onboarding_steps is not None:
            self.set_onboarding_steps(onboarding_steps=onboarding_steps)

        # if the sent location is an empty string we should consider it as deleting the location and geolocation
        if location == "":
            self.location = None
            self.geolocation = None

        self.save()

    def add_membership_request(self, user, message=None):
        return CommunityMembershipRequest.create_membership_request(self, user, message)

    def remove_membership_request(self, user):
        CommunityMembershipRequest.delete_membership_request(self, user)

    def get_membership_request(self, user):
        return CommunityMembershipRequest.get_membership_request(self, user)

    def remove_invite(self, user):
        CommunityInvite.delete_community_invite(user_name=user.username, community_name=self.name)

    def add_moderator(self, user):
        user_membership = self.memberships.get(user=user)
        user_membership.is_moderator = True
        user_membership.save()
        return user_membership

    def remove_moderator(self, user):
        user_membership = self.memberships.get(user=user)
        user_membership.is_moderator = False
        user_membership.save()
        return user_membership

    def add_administrator(self, user):
        user_membership = self.memberships.get(user=user)
        user_membership.is_administrator = True
        user_membership.save()
        return user_membership

    def remove_administrator(self, user):
        user_membership = self.memberships.get(user=user)
        user_membership.is_administrator = False
        user_membership.save()
        return user_membership

    def add_member(self, user):
        user_membership = CommunityMembership.create_membership(user=user, community=self)
        return user_membership

    def remove_member(self, user):
        user_membership = self.memberships.get(user=user)
        user_membership.delete()

    def set_categories_with_names(self, categories_names):
        self.clear_categories()
        Category = get_category_model()
        categories = Category.objects.filter(name__in=categories_names)
        self.categories.set(categories)

    def clear_categories(self):
        self.categories.clear()

    def set_topics_with_ids(self, topic_ids):
        self.clear_topics()
        Topic = get_topic_model()
        topics = Topic.objects.filter(id__in=topic_ids)
        self.topics.set(topics)

    def clear_topics(self):
        self.topics.clear()

    def set_sdgs_with_ids(self, sdg_ids):
        self.clear_sdgs()
        Sdg = get_sdg_model()
        sdgs = Sdg.objects.filter(id__in=sdg_ids)
        self.sdgs.set(sdgs)

    def clear_sdgs(self):
        self.sdgs.clear()

    def set_onboarding_steps(self, onboarding_steps):
        OnboardingStep = get_onboarding_step_model()
        OnboardingStep.set_onboarding_steps(community=self, onboarding_steps=onboarding_steps)

    def create_invite(self, creator, invited_user):
        CommunityInvite = get_community_invite_model()
        return CommunityInvite.create_community_invite(creator=creator, invited_user=invited_user, community=self)

    def get_membership_invite(self, user):
        return CommunityInvite.get_membership_invite(self, user)

    def create_pending_invite(self, creator, invited_email_hash):
        CommunityPendingInvite = get_community_pending_invite_model()
        return CommunityPendingInvite.create_community_pending_invite(
            creator=creator, invited_email_hash=invited_email_hash, community=self
        )

    def create_user_ban_log(self, source_user, target_user):
        return self._create_log(action_type="B", source_user=source_user, target_user=target_user)

    def create_user_unban_log(self, source_user, target_user):
        return self._create_log(action_type="U", source_user=source_user, target_user=target_user)

    def create_add_administrator_log(self, source_user, target_user):
        return self._create_log(action_type="AA", source_user=source_user, target_user=target_user)

    def create_remove_administrator_log(self, source_user, target_user):
        return self._create_log(action_type="RA", source_user=source_user, target_user=target_user)

    def create_add_moderator_log(self, source_user, target_user):
        return self._create_log(action_type="AM", source_user=source_user, target_user=target_user)

    def create_remove_moderator_log(self, source_user, target_user):
        return self._create_log(action_type="RM", source_user=source_user, target_user=target_user)

    def create_remove_post_log(self, source_user, target_user):
        return self._create_log(action_type="RP", source_user=source_user, target_user=target_user)

    def create_remove_post_comment_log(self, source_user, target_user):
        return self._create_log(action_type="RPC", source_user=source_user, target_user=target_user)

    def create_remove_post_comment_reply_log(self, source_user, target_user):
        return self._create_log(action_type="RPCR", source_user=source_user, target_user=target_user)

    def create_disable_post_comments_log(self, source_user, target_user, post):
        return self._create_log(
            action_type="DPC",
            post=post,
            source_user=source_user,
            target_user=target_user,
        )

    def create_enable_post_comments_log(self, source_user, target_user, post):
        return self._create_log(
            action_type="EPC",
            post=post,
            source_user=source_user,
            target_user=target_user,
        )

    def create_open_post_log(self, source_user, target_user, post):
        return self._create_log(
            action_type="OP",
            post=post,
            source_user=source_user,
            target_user=target_user,
        )

    def create_close_post_log(self, source_user, target_user, post):
        return self._create_log(
            action_type="CP",
            post=post,
            source_user=source_user,
            target_user=target_user,
        )

    def _create_log(self, action_type, source_user, target_user, post=None):
        CommunityModeratorUserActionLog = get_community_log_model()
        return CommunityModeratorUserActionLog.create_community_log(
            community=self,
            post=post,
            target_user=target_user,
            action_type=action_type,
            source_user=source_user,
        )

    def save(self, *args, **kwargs):
        """On save, update timestamps"""
        if not self.created:
            self.created = timezone.now()

        if not self.name:
            hash = sha256(str(self).encode("utf-8")).hexdigest()
            self.name = create_community_name_from_title_and_hash(self.title, hash)

        if self.user_adjective:
            self.user_adjective = self.user_adjective.title()

        if self.users_adjective:
            self.users_adjective = self.users_adjective.title()

        return super(Community, self).save(*args, **kwargs)

    def delete_notifications(self):
        # Remove all community new post notifications
        CommunityNewPostNotification = get_community_new_post_notification_model()
        CommunityNewPostNotification.objects.filter(
            community_notifications_subscription__community_id=self.pk
        ).delete()

        # Remove all community invite notifications
        CommunityInviteNotification = get_community_invite_notification_model()
        CommunityInviteNotification.objects.filter(community_invite__community_id=self.pk).delete()

    def delete_pending_notifications(self):
        for membership_request in self.membership_requests.all():
            membership_request.delete_notifications()
        for membership_invite in self.invites.all():
            membership_invite.delete_notifications()

    def delete_pending_notifications_for_user(self, username):
        for membership_request in self.membership_requests.all():
            NotificationApi.delete_in_app_messages(
                transaction_id=str(membership_request.id), subscriber_id=str(username)
            )
        for membership_invite in self.invites.all():
            NotificationApi.delete_in_app_messages(
                transaction_id=str(membership_invite.id), subscriber_id=str(username)
            )

    def soft_delete(self):
        self.is_deleted = True
        for post in self.posts.all().iterator():
            post.soft_delete()
        self.save()

    def unsoft_delete(self):
        self.is_deleted = False
        for post in self.posts:
            post.unsoft_delete()
        self.save()

    def count_pending_moderated_objects(self):
        return self.moderated_objects.filter(status=ModeratedObject.STATUS_PENDING).count()

    def connection_status_to_user(self, user) -> List[Optional[SpaceUserConnectionType]]:
        if user.is_anonymous:
            return []

        roles = []

        if user.are_new_post_notifications_enabled_for_community(self):
            roles.append(SpaceUserConnectionType.FOLLOWER)

        if user.is_membership_requestor_of_community_with_name(self.name):
            roles.append(SpaceUserConnectionType.MEMBERSHIP_REQUESTOR)

        if user.is_invited_to_community_with_name(self.name):
            roles.append(SpaceUserConnectionType.MEMBERSHIP_INVITEE)

        if self.creator == user:
            roles.append(SpaceUserConnectionType.CREATOR)

        if membership := self.memberships.filter(user=user).first():
            roles.append(SpaceUserConnectionType.MEMBER)

            if membership.is_administrator:
                roles.append(SpaceUserConnectionType.ADMINISTRATOR)

            # if membership.is_moderator:
            #     roles.append(SpaceUserConnectionType.MODERATOR)

        return roles

    def _update_cover(self, cover, save=True):
        if cover is None:
            self._delete_cover(save=False)
        else:
            self.cover = cover
            self.cover_blurhash = generate_blurhash(cover)
        if save:
            self.save()

    def _delete_cover(self, save=True):
        delete_file_field(self.cover)
        self.cover = None
        self.cover_blurhash = None
        self.cover.delete(save=save)

    def _update_avatar(self, avatar, save=True):
        if avatar is None:
            self._delete_avatar(save=False)
        else:
            self.avatar = avatar
            self.avatar_blurhash = generate_blurhash(avatar)

        if save:
            self.save()

    def _delete_avatar(self, save=True):
        delete_file_field(self.avatar)
        self.avatar = None
        self.avatar_blurhash = None
        self.avatar.delete(save=save)

    def __str__(self):
        return f"{self.title} ({self.id})"


class CommunityMembership(ModelWithUUID):
    """
    An object representing the membership of a user in a community
    """

    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="communities_memberships",
        null=False,
        blank=False,
    )

    community = models.ForeignKey(
        Community,
        on_delete=models.CASCADE,
        related_name="memberships",
        null=False,
        blank=False,
    )

    is_administrator = models.BooleanField(_("is administrator"), default=False)
    is_moderator = models.BooleanField(_("is moderator"), default=False)
    created = models.DateTimeField(editable=False)

    class Meta:
        unique_together = (("user", "community"),)
        indexes = [
            models.Index(fields=["community", "user"]),
            models.Index(fields=["community", "user", "is_administrator"]),
            models.Index(fields=["community", "user", "is_moderator"]),
        ]

    @classmethod
    def create_membership(cls, user, community, is_administrator=False, is_moderator=False):
        membership = cls.objects.create(
            user=user,
            community=community,
            is_administrator=is_administrator,
            is_moderator=is_moderator,
        )

        return membership

    @classmethod
    def has_other_admins(cls, community_id, user_id):
        return cls.objects.filter(community_id=community_id, is_administrator=True).exclude(user_id=user_id).exists()

    @classmethod
    def has_other_members(cls, community_id, user_id):
        return cls.objects.filter(community_id=community_id).exclude(user_id=user_id).exists()

    def save(self, *args, **kwargs):
        """On save, update timestamps"""
        if not self.created:
            self.created = timezone.now()
        return super(CommunityMembership, self).save(*args, **kwargs)


class CommunityLog(ModelWithUUID):
    """
    A log for community moderators user actions such as banning/unbanning
    """

    source_user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="+", null=False, blank=False)
    target_user = models.ForeignKey(User, on_delete=models.SET_NULL, related_name="+", null=True, blank=False)
    post = models.ForeignKey(Post, on_delete=models.CASCADE, related_name="+", null=True, blank=True)
    community = models.ForeignKey(
        Community,
        on_delete=models.CASCADE,
        related_name="logs",
        null=False,
        blank=False,
    )
    created = models.DateTimeField(editable=False)

    ACTION_TYPES = (
        ("B", "Ban"),
        ("U", "Unban"),
        ("AM", "Add Moderator"),
        ("RM", "Remove Moderator"),
        ("AA", "Add Administrator"),
        ("RA", "Remove Administrator"),
        ("OP", "Open Post"),
        ("CP", "Close Post"),
        ("RP", "Remove Post"),
        ("RPC", "Remove Post Comment"),
        ("DPC", "Disable Post Comments"),
        ("EPC", "Enable Post Comments"),
    )
    action_type = models.CharField(editable=False, blank=False, null=False, choices=ACTION_TYPES, max_length=5)

    @classmethod
    def create_community_log(cls, community, action_type, source_user, target_user, post=None):
        return cls.objects.create(
            community=community,
            action_type=action_type,
            source_user=source_user,
            target_user=target_user,
            post=post,
        )

    def save(self, *args, **kwargs):
        """On save, update timestamps"""
        if not self.created:
            self.created = timezone.now()
        return super(CommunityLog, self).save(*args, **kwargs)


class CommunityMembershipRequest(ModelWithUUID):
    community = models.ForeignKey(
        Community,
        on_delete=models.CASCADE,
        related_name="membership_requests",
        null=False,
        blank=False,
    )

    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="community_membership_requests",
        null=False,
        blank=False,
    )

    message = models.TextField(
        max_length=settings.COMMUNITY_MEMBERSHIP_REQUEST_MESSAGE_MAX_LENGTH,
        blank=True,
        null=True,
    )

    class Meta:
        unique_together = ("community", "user")
        indexes = [
            models.Index(fields=["community", "user"]),
        ]

    @classmethod
    def create_membership_request(cls, community, user, message=None):
        return cls.objects.create(community=community, user=user, message=message)

    @classmethod
    def delete_membership_request(cls, community, user):
        cls.objects.filter(community=community, user=user).delete()

    @classmethod
    def get_membership_request(cls, community, user):
        return cls.objects.get(community=community, user=user)

    def delete_notifications(self):
        transaction_id = str(self.id)
        NotificationApi.cancel_workflow(transaction_id=transaction_id)
        NotificationApi.delete_in_app_messages(transaction_id=transaction_id)


class CommunityPendingInvite(ModelWithUUID):
    creator = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="created_communities_pending_invites",
        null=False,
        blank=False,
    )
    invited_email_hash = models.TextField(
        blank=False,
        null=False,
    )
    community = models.ForeignKey(
        Community,
        on_delete=models.CASCADE,
        related_name="pending_invites",
        null=False,
        blank=False,
    )

    class Meta:
        unique_together = (("invited_email_hash", "community"),)

    @classmethod
    def create_community_pending_invite(cls, creator, invited_email_hash, community):
        return cls.objects.create(creator=creator, invited_email_hash=invited_email_hash, community=community)

    @classmethod
    def is_email_invited_to_community(cls, invited_email_hash, community):
        return cls.objects.filter(community__name=community.name, invited_email_hash=invited_email_hash).exists()


class CommunityInvite(ModelWithUUID):
    creator = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        related_name="created_communities_invites",
        null=True,
        blank=False,
    )
    invited_user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="communities_invites",
        null=False,
        blank=False,
    )
    community = models.ForeignKey(
        Community,
        on_delete=models.CASCADE,
        related_name="invites",
        null=False,
        blank=False,
    )

    class Meta:
        unique_together = (("invited_user", "community", "creator"),)

    @classmethod
    def create_community_invite(cls, creator, invited_user, community):
        return cls.objects.create(creator=creator, invited_user=invited_user, community=community)

    @classmethod
    def get_membership_invite(cls, community, user):
        return cls.objects.get(community=community, invited_user=user)

    @classmethod
    def delete_community_invite(cls, user_name, community_name):
        return cls.objects.filter(community__name=community_name, invited_user__username=user_name).delete()

    @classmethod
    def is_user_with_username_invited_to_community_with_name(cls, username, community_name):
        return cls.objects.filter(community__name=community_name, invited_user__username=username).exists()

    def delete_notifications(self):
        transaction_id = str(self.id)
        NotificationApi.cancel_workflow(transaction_id=transaction_id)
        NotificationApi.delete_in_app_messages(transaction_id=transaction_id)


class CommunityNotificationsSubscription(ModelWithUUID):
    subscriber = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="community_notifications_subscriptions",
        null=False,
        blank=False,
    )
    community = models.ForeignKey(
        Community,
        on_delete=models.CASCADE,
        related_name="notifications_subscriptions",
        null=False,
        blank=False,
    )
    new_post_notifications = models.BooleanField(default=False, blank=False)

    class Meta:
        unique_together = (
            "community",
            "subscriber",
        )

    @classmethod
    def enable_new_post_notification_for_community(cls, community, subscriber):
        cls._set_new_post_notification(community, subscriber, True)

    @classmethod
    def disable_new_post_notification_for_community(cls, community, subscriber):
        cls._set_new_post_notification(community, subscriber, False)

    @classmethod
    def _set_new_post_notification(cls, community, subscriber, value):
        subscription = cls._get_or_create_community_notifications_subscription(
            community=community, subscriber=subscriber
        )
        subscription.new_post_notifications = value
        subscription.save()

    @classmethod
    def _create_community_notifications_subscription(cls, subscriber, community):
        if not cls.objects.filter(community=community, subscriber=subscriber).exists():
            return cls.objects.create(subscriber=subscriber, community=community)

        community_notifications_subscription = cls.objects.get(subscriber=subscriber, community=community)
        community_notifications_subscription.save()

        return community_notifications_subscription

    @classmethod
    def _get_or_create_community_notifications_subscription(cls, subscriber, community):
        try:
            community_notifications_subscription = cls.objects.get(
                subscriber_id=subscriber.pk, community_id=community.pk
            )
        except cls.DoesNotExist:
            community_notifications_subscription = cls._create_community_notifications_subscription(
                subscriber=subscriber, community=community
            )

        return community_notifications_subscription

    @classmethod
    def delete_community_notifications_subscription(cls, subscriber, community):
        return cls.objects.filter(subscriber=subscriber, community=community).delete()

    @classmethod
    def community_notifications_subscription_exists(cls, subscriber, community):
        return cls.objects.filter(subscriber=subscriber, community=community).exists()

    @classmethod
    def are_new_post_notifications_enabled_for_user_with_username_and_community_with_name(
        cls, username, community_name
    ):
        return cls.objects.filter(
            community__name=community_name,
            subscriber__username=username,
            new_post_notifications=True,
        ).exists()


class Task(ModelWithUUID):
    @strawberry.enum
    class LocationType(models.TextChoices):
        HYBRID = ("HYBRID",)
        REMOTE = ("REMOTE",)
        ONSITE = "ONSITE"

    @strawberry.enum
    class Regularity(models.TextChoices):
        REGULARLY = ("REGULARLY",)
        PROJECT_BASED = ("PROJECT_BASED",)
        ONE_TIME = "ONE_TIME"

    name = models.CharField(
        max_length=settings.TASK_NAME_MAX_LENGTH,
        blank=False,
    )
    description = models.TextField(
        blank=False,
        max_length=settings.TASK_DESCRIPTION_MAX_LENGTH,
    )
    community = models.ForeignKey(
        Community,
        on_delete=models.CASCADE,
        related_name="tasks",
        blank=False,
        null=False,
    )
    creator = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        related_name="created_tasks",
        blank=True,
        null=True,
    )
    created = models.DateTimeField(default=timezone.now, editable=False)
    slots_available = models.PositiveIntegerField(blank=False)
    slots_taken = models.PositiveIntegerField(blank=False, default=0)
    visibility = models.CharField(max_length=12, choices=VisibilityType.choices, default=VisibilityType.PUBLIC)
    location_type = models.CharField(max_length=6, choices=LocationType.choices, default=LocationType.REMOTE)
    location = models.CharField(
        max_length=settings.TASK_LOCATION_MAX_LENGTH,
        blank=True,
        null=True,
        db_index=True,
    )
    geolocation = models.PointField(blank=True, null=True, spatial_index=True)
    regularity = models.CharField(
        max_length=13,
        choices=Regularity.choices,
    )
    skills = models.ManyToManyField(Skill, related_name="tasks", blank=True, db_index=True)
    thumbnail = ProcessedImageField(
        storage=community_task_image_storage,
        verbose_name=_("thumbnail"),
        blank=True,
        null=True,
        upload_to=upload_to_community_task_thumbnail_directory,
        processors=[
            ExifRotate(),
            ResizeToFit(
                width=settings.CONTENT_IMAGE_MAX_DIMENSION,
                height=settings.CONTENT_IMAGE_MAX_DIMENSION,
                upscale=False,
            ),
        ],
        max_length=settings.IMAGE_URL_MAX_LENGTH,
    )
    thumbnail_blurhash = models.CharField(max_length=50, blank=True, null=True)
    contact_email = models.EmailField(
        _("contact email"),
        blank=False,
        null=True,
    )
    contact_phone = models.CharField(
        max_length=settings.COMMUNITY_CONTACT_PHONE_MAX_LENGTH,
        blank=True,
        null=True,
    )

    @staticmethod
    def is_visible_query(user, prefix=None):
        pQ = PrefixedQ(prefix)

        if user.is_anonymous:
            return pQ(visibility=VisibilityType.PUBLIC)

        return pQ(visibility=VisibilityType.PUBLIC) | pQ(community__memberships__user__id=user.id)

    def clear_skills(self):
        self.skills.clear()

    def set_skills_with_ids(self, skill_ids):
        self.clear_skills()
        Skill = get_skill_model()
        skills = Skill.objects.filter(id__in=skill_ids)
        self.skills.set(skills)

    @classmethod
    def create_task(
        cls,
        creator,
        community,
        name,
        description,
        visibility,
        location_type,
        contact_email,
        slots_available,
        location=None,
        geolocation=None,
        regularity=None,
        contact_phone=None,
        skills=None,
        thumbnail=None,
    ):
        task = cls.objects.create(
            creator=creator,
            community=community,
            name=name,
            description=description,
            visibility=visibility,
            location_type=location_type,
            contact_email=contact_email,
            slots_available=slots_available,
            location=location,
            geolocation=geolocation,
            regularity=regularity,
            contact_phone=contact_phone,
            thumbnail=thumbnail,
            thumbnail_blurhash=generate_blurhash(thumbnail),
        )

        if skills:
            task.set_skills_with_ids(skill_ids=skills)

        task.save()
        return task

    def update(
        self,
        name,
        description,
        visibility,
        location_type,
        contact_email,
        slots_available,
        location=None,
        geolocation=None,
        regularity=None,
        contact_phone=None,
        skills=None,
        thumbnail=None,
        remove_thumbnail=False,
    ):
        self.name = name
        self.description = description
        self.visibility = visibility
        self.location_type = location_type
        self.contact_email = contact_email
        self.regularity = regularity
        self.slots_available = slots_available

        if location is not None:
            self.location = location
        if geolocation is not None:
            self.geolocation = geolocation
        if contact_phone is not None:
            self.contact_phone = contact_phone
        if skills is not None:
            self.skills.set(skills)

        if remove_thumbnail:
            self._delete_thumbnail(save=False)
        elif thumbnail:
            self._update_thumbnail(thumbnail, save=False)

        self.save()
        return self

    def _update_thumbnail(self, thumbnail, save=True):
        if self.thumbnail:
            self._delete_thumbnail(save=False)
        self.thumbnail = thumbnail
        self.thumbnail_blurhash = generate_blurhash(thumbnail)

        if save:
            self.save()

    def _delete_thumbnail(self, save=True):
        delete_file_field(self.thumbnail)
        self.thumbnail = None
        self.thumbnail_blurhash = None
        self.thumbnail.delete(save=save)


@strawberry.enum
class ExternalLinkType(models.TextChoices):
    INSTAGRAM = "instagram", _("instagram")
    FACEBOOK = "facebook", _("facebook")
    LINKEDIN = "linkedin", _("linkedin")
    DISCORD = "discord", _("discord")
    TWITTER = "twitter", _("twitter")
    WHATSAPP = "whatsapp", _("whatsapp")
    OTHER = "other", _("other")


class ExternalLink(ModelWithUUID):
    url = models.TextField(blank=False)
    community = models.ForeignKey(
        Community,
        on_delete=models.CASCADE,
        related_name="links",
        blank=False,
        null=False,
    )
    type = models.CharField(
        max_length=9,
        choices=ExternalLinkType.choices,
    )
    name = models.CharField(
        max_length=settings.EXTERNAL_LINK_NAME_MAX_LENGTH,
    )

    @classmethod
    def create(
        cls,
        community,
        url,
        type,
        name,
    ):
        external_link = cls.objects.create(
            community=community,
            url=url,
            type=type,
            name=name,
        )

        return external_link

    def update(
        self,
        url=None,
        type=None,
        name=None,
    ):
        if url is not None:
            self.url = url
        if type is not None:
            self.type = type
        if name is not None:
            self.name = name

        self.save()


class CollaborationTool(ModelWithUUID):
    @strawberry.enum
    class CollectionType(models.TextChoices):
        COLLABORATION = "COLLABORATION"
        COMMUNICATION = "COMMUNICATION"
        CALENDARS = "CALENDARS"
        SURVEYS = "SURVEYS"
        GOOD_TO_KNOW = "GOOD_TO_KNOW"
        INFO_MATERIAL = "INFO_MATERIAL"
        USED_SERVICES = "USED_SERVICES"
        OTHERS = "OTHERS"

    url = models.URLField(blank=False, max_length=settings.COLLABORATION_TOOL_URL_MAX_LENGTH)
    title = models.CharField(blank=False, max_length=settings.COLLABORATION_TOOL_TITLE_MAX_LENGTH)
    collection_type = models.CharField(
        max_length=15,
        choices=CollectionType.choices,
    )
    description = models.CharField(
        max_length=settings.COLLABORATION_TOOL_DESCRIPTION_MAX_LENGTH,
        null=True,
        blank=True,
    )
    domain = models.CharField(max_length=settings.COLLABORATION_TOOL_DOMAIN_MAX_LENGTH, blank=False)
    creator = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        related_name="created_collaboration_tools",
        null=True,
    )
    community = models.ForeignKey(
        Community,
        on_delete=models.CASCADE,
        related_name="collaboration_tools",
        blank=False,
        null=False,
    )
    created_at = models.DateTimeField(auto_now_add=True)
    thumbnail = ProcessedImageField(
        storage=community_task_image_storage,
        verbose_name=_("thumbnail"),
        blank=True,
        null=True,
        upload_to=upload_to_community_task_thumbnail_directory,
        processors=[
            ExifRotate(),
            ResizeToFit(
                width=settings.CONTENT_IMAGE_MAX_DIMENSION,
                height=settings.CONTENT_IMAGE_MAX_DIMENSION,
                upscale=False,
            ),
        ],
        max_length=settings.IMAGE_URL_MAX_LENGTH,
    )
    thumbnail_blurhash = models.CharField(max_length=50, blank=True, null=True)

    def _update_thumbnail(self, thumbnail, save=True):
        if self.thumbnail:
            self._delete_thumbnail(save=False)
        self.thumbnail = thumbnail
        self.thumbnail_blurhash = generate_blurhash(thumbnail)

        if save:
            self.save()

    def _delete_thumbnail(self, save=True):
        delete_file_field(self.thumbnail)
        self.thumbnail = None
        self.thumbnail_blurhash = None
        self.thumbnail.delete(save=save)

    def update(
        self,
        url=None,
        title=None,
        description=None,
        collection_type=None,
        thumbnail=None,
        remove_thumbnail=False,
    ):
        if url is not None:
            self.url = url
            self.domain = extract_and_capitalize_domain_name(url)

        if title is not None:
            self.title = title

        if description is not None:
            self.description = description

        if collection_type is not None:
            self.collection_type = collection_type

        if remove_thumbnail:
            self._delete_thumbnail(save=False)
        elif thumbnail is not None:
            self._update_thumbnail(thumbnail, save=False)

        self.save()

    @classmethod
    def add_collaboration_tool(
        cls,
        creator,
        community,
        url,
        title,
        collection_type,
        description=None,
        thumbnail=None,
    ):
        collaboration_tool = cls.objects.create(
            creator=creator,
            community=community,
            url=url,
            domain=extract_and_capitalize_domain_name(url),
            title=title,
            collection_type=collection_type,
            description=description,
            thumbnail=thumbnail,
        )

        collaboration_tool.save()
        return collaboration_tool


class OnboardingStep(ModelWithUUID):
    community = models.ForeignKey(
        Community,
        on_delete=models.CASCADE,
        related_name="onboarding_steps",
        blank=False,
        null=False,
    )
    text = models.CharField(max_length=settings.ONBOARDING_STEP_TEXT_MAX_LENGTH, null=True, blank=True)
    step_number = models.PositiveSmallIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = (("community", "step_number"),)
        indexes = [
            models.Index(fields=["community", "step_number"]),
        ]

    def update(
        self,
        text=None,
        step_number=None,
    ):
        if text is not None:
            self.text = text

        if step_number is not None:
            self.step_number = step_number

        self.save()

    @classmethod
    def set_onboarding_steps(
        cls,
        community,
        onboarding_steps,
    ):
        with transaction.atomic():
            old_steps = cls.objects.filter(community=community).order_by("step_number")
            new_step_count = len(onboarding_steps)
            old_step_count = len(old_steps)
            common_length = min(new_step_count, old_step_count)

            # Overwrite texts of old steps
            for index in range(common_length):
                new_step = onboarding_steps[index]
                old_steps[index].update(
                    text=new_step["text"],
                )

            # Create new steps if there are not enough
            for index in range(common_length, new_step_count):
                new_step = onboarding_steps[index]
                step = cls.objects.create(
                    community=community,
                    text=new_step["text"],
                    step_number=index,
                )
                step.save()

            # Remove old steps if there are too many
            for index in range(common_length, old_step_count):
                old_steps[index].delete()

        return community


from .network_relationship import SpacesRelationship  # noqa: F401
