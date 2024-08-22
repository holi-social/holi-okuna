from collections import OrderedDict

from django.conf import settings
from rest_framework import serializers
from django.contrib.gis import geos
from django.core.exceptions import ImproperlyConfigured

from openbook_auth.models import User, UserProfile
from openbook_circles.models import Circle
from openbook_common.models import AppVersion, Emoji, EmojiGroup, Badge, Language, LinkPreview
from openbook_common.serializers_fields.user import IsFollowingField, IsFollowedField
from openbook_common.types import GeolocationFeature
from openbook_communities.models import Community, CommunityMembership
from openbook_communities.serializers_fields import (
    IsFavoriteField,
    CommunityMembershipsField,
)
from openbook_communities.validators import (
    community_name_characters_validator,
    community_name_exists,
)
from openbook_follows.models import FollowRequest, Follow
from openbook_hashtags.models import Hashtag
from openbook_posts.models import PostReaction, PostImage


class CommonEmojiSerializer(serializers.ModelSerializer):
    class Meta:
        model = Emoji

        fields = (
            "id",
            "keyword",
            "image",
            "created",
            "order",
        )


class CommonEmojiGroupSerializer(serializers.ModelSerializer):
    emojis = serializers.SerializerMethodField()

    def get_emojis(self, obj):
        emojis = obj.emojis.all().order_by("order")

        request = self.context["request"]
        return CommonEmojiSerializer(emojis, many=True, context={"request": request}).data

    class Meta:
        model = EmojiGroup

        fields = (
            "id",
            "keyword",
            "color",
            "created",
            "order",
            "emojis",
        )


class CommonUserProfileBadgeSerializer(serializers.ModelSerializer):
    class Meta:
        model = Badge
        fields = ("keyword", "keyword_description")


class CommonPostCreatorBadgeSerializer(serializers.ModelSerializer):
    class Meta:
        model = Badge
        fields = ("keyword", "keyword_description")


class CommonPostEmojiCountSerializer(serializers.Serializer):
    reaction_type = serializers.CharField()
    count = serializers.IntegerField(
        required=True,
    )


class CommonPostCommunitySerializer(serializers.ModelSerializer):
    class Meta:
        model = Community
        fields = ("id", "name", "avatar")


class CommonPostReactionSerializer(serializers.ModelSerializer):
    class Meta:
        model = PostReaction
        fields = ("reaction_type", "id")


class CommonPostLanguageSerializer(serializers.ModelSerializer):
    class Meta:
        model = Language
        fields = (
            "id",
            "code",
            "name",
        )


class CommonPostImageSerializer(serializers.ModelSerializer):
    image = serializers.ImageField(read_only=True)

    class Meta:
        model = PostImage
        fields = ("image", "width", "height")


class CommonCommunityMembershipSerializer(serializers.ModelSerializer):
    class Meta:
        model = CommunityMembership
        fields = (
            "id",
            "user_id",
            "community_id",
            "is_administrator",
            "is_moderator",
        )


class CommonHashtagSerializer(serializers.ModelSerializer):
    emoji = CommonEmojiSerializer()

    class Meta:
        model = Hashtag
        fields = ("id", "name", "color", "text_color", "image", "emoji")


class LinkPreviewSerializer(serializers.ModelSerializer):
    class Meta:
        model = LinkPreview
        fields = (
            "requested_url",
            "url",
            "title",
            "description",
            "type",
            "image",
            "fetched_at",
        )


class CommonCircleSerializer(serializers.ModelSerializer):
    class Meta:
        model = Circle
        fields = ("id", "name", "color", "users_count")


class CommonSearchCommunitiesSerializer(serializers.Serializer):
    count = serializers.IntegerField(required=False, max_value=20)
    query = serializers.CharField(
        max_length=max(settings.COMMUNITY_NAME_MAX_LENGTH, settings.COMMUNITY_TITLE_MAX_LENGTH),
        allow_blank=False,
        required=True,
    )

    excluded_from_profile_posts = serializers.BooleanField(required=False, default=True)


class CommonSearchCommunitiesCommunitySerializer(serializers.ModelSerializer):
    is_favorite = IsFavoriteField()

    memberships = CommunityMembershipsField(community_membership_serializer=CommonCommunityMembershipSerializer)

    class Meta:
        model = Community
        fields = (
            "id",
            "name",
            "title",
            "avatar",
            "cover",
            "members_count",
            "color",
            "user_adjective",
            "users_adjective",
            "is_favorite",
            "memberships",
        )


class CommonCommunityNameSerializer(serializers.Serializer):
    community_name = serializers.CharField(
        max_length=settings.COMMUNITY_NAME_MAX_LENGTH,
        allow_blank=False,
        required=True,
        validators=[community_name_characters_validator, community_name_exists],
    )


class CommonBadgeSerializer(serializers.ModelSerializer):
    class Meta:
        model = Badge
        fields = ("keyword", "keyword_description")


class CommonPublicUserProfileSerializer(serializers.ModelSerializer):
    badges = CommonBadgeSerializer(many=True)

    class Meta:
        model = UserProfile
        fields = (
            "id",
            "avatar",
            "cover",
            "name",
            "badges",
        )


class CommonPublicUserSerializer(serializers.ModelSerializer):
    profile = CommonPublicUserProfileSerializer()
    is_following = IsFollowingField()
    is_followed = IsFollowedField()

    class Meta:
        model = User
        fields = (
            "id",
            "username",
            "profile",
            "visibility",
            "is_following",
            "is_followed",
        )


class CommonFollowRequestSerializer(serializers.ModelSerializer):
    creator = CommonPublicUserSerializer()
    target_user = CommonPublicUserSerializer()

    class Meta:
        model = FollowRequest
        fields = (
            "id",
            "creator",
            "target_user",
        )


class CommonFollowSerializer(serializers.ModelSerializer):
    followed_user = CommonPublicUserSerializer(many=False)

    class Meta:
        model = Follow
        fields = (
            "id",
            "user",
            "lists",
            "followed_user",
        )


class ProxyDomainCheckSerializer(serializers.Serializer):
    url = serializers.CharField(
        required=True,
    )


class GeolocationPointSerializer(serializers.Serializer):
    longitude = serializers.FloatField()
    latitude = serializers.FloatField()


# GeoFeatureModelSerializer + GeoFeatureModelListSerializer copied from https://github.com/openwisp/django-rest-framework-gis/blob/master/rest_framework_gis/serializers.py


class GeoFeatureModelListSerializer(serializers.ListSerializer):
    @property
    def data(self):
        return super(serializers.ListSerializer, self).data

    def to_representation(self, data):
        """
        Add GeoJSON compatible formatting to a serialized queryset list
        """
        return OrderedDict(
            (
                ("type", "FeatureCollection"),
                ("features", super().to_representation(data)),
            )
        )


class GeoFeatureModelSerializer(serializers.ModelSerializer):
    """
    A subclass of ModelSerializer
    that outputs geojson-ready data as
    features and feature collections
    """

    @classmethod
    def many_init(cls, *args, **kwargs):
        child_serializer = cls(*args, **kwargs)
        list_kwargs = {"child": child_serializer}
        list_kwargs.update({key: value for key, value in kwargs.items() if key in serializers.LIST_SERIALIZER_KWARGS})
        meta = getattr(cls, "Meta", None)
        list_serializer_class = getattr(meta, "list_serializer_class", GeoFeatureModelListSerializer)
        return list_serializer_class(*args, **list_kwargs)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        meta = self.Meta
        default_id_field = None
        primary_key = self.Meta.model._meta.pk.name
        # use primary key as id_field when possible
        if not hasattr(meta, "fields") or meta.fields == "__all__" or primary_key in meta.fields:
            default_id_field = primary_key
        meta.id_field = getattr(meta, "id_field", default_id_field)

        if not hasattr(meta, "geo_field") or not meta.geo_field:
            raise ImproperlyConfigured("You must define a 'geo_field'.")

        def check_excludes(field_name, field_role):
            """make sure the field is not excluded"""
            if hasattr(meta, "exclude") and field_name in meta.exclude:
                raise ImproperlyConfigured("You cannot exclude your '{0}'.".format(field_role))

        def add_to_fields(field_name):
            """Make sure the field is included in the fields"""
            if hasattr(meta, "fields") and meta.fields != "__all__":
                if field_name not in meta.fields:
                    if type(meta.fields) is tuple:
                        additional_fields = (field_name,)
                    else:
                        additional_fields = [field_name]
                    meta.fields += additional_fields

        check_excludes(meta.geo_field, "geo_field")
        add_to_fields(meta.geo_field)

        meta.bbox_geo_field = getattr(meta, "bbox_geo_field", None)
        if meta.bbox_geo_field:
            check_excludes(meta.bbox_geo_field, "bbox_geo_field")
            add_to_fields(meta.bbox_geo_field)

        meta.auto_bbox = getattr(meta, "auto_bbox", False)
        if meta.bbox_geo_field and meta.auto_bbox:
            raise ImproperlyConfigured(
                "You must eiher define a 'bbox_geo_field' or " "'auto_bbox', but you can not set both"
            )

    def to_representation(self, instance):
        """
        Serialize objects -> primitives.
        """
        # prepare OrderedDict geojson structure
        feature = OrderedDict()

        # keep track of the fields being processed
        processed_fields = set()

        # optional id attribute
        if self.Meta.id_field:
            field = self.fields[self.Meta.id_field]
            value = field.get_attribute(instance)
            feature["id"] = field.to_representation(value)
            processed_fields.add(self.Meta.id_field)

        # required type attribute
        # must be "Feature" according to GeoJSON spec
        feature["type"] = "Feature"

        # required geometry attribute
        # MUST be present in output according to GeoJSON spec
        field = self.fields[self.Meta.geo_field]
        geo_value = field.get_attribute(instance)
        feature["geometry"] = field.to_representation(geo_value)
        processed_fields.add(self.Meta.geo_field)

        # Bounding Box
        # if auto_bbox feature is enabled
        # bbox will be determined automatically automatically
        if self.Meta.auto_bbox and geo_value:
            feature["bbox"] = geo_value.extent
        # otherwise it can be determined via another field
        elif self.Meta.bbox_geo_field:
            field = self.fields[self.Meta.bbox_geo_field]
            value = field.get_attribute(instance)
            feature["bbox"] = value.extent if hasattr(value, "extent") else None
            processed_fields.add(self.Meta.bbox_geo_field)

        # the list of fields that will be processed by get_properties
        # we will remove fields that have been already processed
        # to increase performance on large numbers
        fields = [field_value for field_key, field_value in self.fields.items() if field_key not in processed_fields]

        # GeoJSON properties
        feature["properties"] = self.get_properties(instance, fields)

        return feature

    def get_properties(self, instance, fields):
        """
        Get the feature metadata which will be used for the GeoJSON
        "properties" key.

        By default it returns all serializer fields excluding those used for
        the ID, the geometry and the bounding box.

        :param instance: The current Django model instance
        :param fields: The list of fields to process (fields already processed have been removed)
        :return: OrderedDict containing the properties of the current feature
        :rtype: OrderedDict
        """
        properties = OrderedDict()

        for field in fields:
            if field.write_only:
                continue
            value = field.get_attribute(instance)
            representation = None
            if value is not None:
                representation = field.to_representation(value)
            properties[field.field_name] = representation

        return properties

    def to_internal_value(self, data):
        """
        Override the parent method to first remove the GeoJSON formatting
        """
        if "properties" in data:
            data = self.unformat_geojson(data)
        return super().to_internal_value(data)

    def unformat_geojson(self, feature):
        """
        This function should return a dictionary containing keys which maps
        to serializer fields.

        Remember that GeoJSON contains a key "properties" which contains the
        feature metadata. This should be flattened to make sure this
        metadata is stored in the right serializer fields.

        :param feature: The dictionary containing the feature data directly
                        from the GeoJSON data.
        :return: A new dictionary which maps the GeoJSON values to
                 serializer fields
        """
        attrs = feature["properties"]

        if "geometry" in feature:
            attrs[self.Meta.geo_field] = feature["geometry"]

        if self.Meta.id_field and "id" in feature:
            attrs[self.Meta.id_field] = feature["id"]

        if self.Meta.bbox_geo_field and "bbox" in feature:
            attrs[self.Meta.bbox_geo_field] = geos.Polygon.from_bbox(feature["bbox"])

        return attrs


class GeolocationFeatureSerializer(GeoFeatureModelSerializer):
    class Meta:
        model = UserProfile
        geo_field = "geolocation"
        fields = ("geolocation",)

    def to_internal_value(self, data):
        return GeolocationFeature.from_geojson(data)


class AppVersionSerializer(serializers.ModelSerializer):
    class Meta:
        model = AppVersion
        fields = (
            "version",
            "build_number",
        )
