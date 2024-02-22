from __future__ import annotations
import uuid
from urllib.parse import urlparse, urljoin, urlsplit

from django.conf import settings
from django.contrib.gis.db import models
from django.contrib.gis.db.models import Q
from django.utils import timezone
from django.utils.translation import gettext_lazy as _
from ordered_model.models import OrderedModel
from requests import RequestException

from openbook.settings import COLOR_ATTR_MAX_LENGTH
from openbook_common.helpers import extract_urls_from_string, attr_filled
from openbook_common.enums import NeedUpdateType, FeatureToggleType
from openbook_common.utils.helpers import normalize_url
from openbook_common.validators import hex_color_validator
import tldextract
import requests
from bs4 import BeautifulSoup
from typing import List


class ModelWithUUID(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    class Meta:
        abstract = True


class OrderedModelWithUUID(OrderedModel):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    class Meta:
        abstract = True
        ordering = ("order",)


class EmojiGroup(ModelWithUUID):
    keyword = models.CharField(_("keyword"), max_length=32, blank=False, null=False)
    color = models.CharField(
        _("color"),
        max_length=COLOR_ATTR_MAX_LENGTH,
        blank=False,
        null=False,
        validators=[hex_color_validator],
        unique=False,
    )
    order = models.IntegerField(unique=False, default=100)
    created = models.DateTimeField(editable=False)
    is_reaction_group = models.BooleanField(_("is reaction group"), default=False)

    def __str__(self):
        return "EmojiGroup: " + self.keyword

    def save(self, *args, **kwargs):
        """On save, update timestamps"""
        if not self.created:
            self.created = timezone.now()
        return super(EmojiGroup, self).save(*args, **kwargs)

    def has_emoji_with_id(self, emoji_id):
        return self.emojis.filter(pk=emoji_id).exists()


class Emoji(ModelWithUUID):
    group = models.ForeignKey(EmojiGroup, on_delete=models.CASCADE, related_name="emojis", null=True)
    keyword = models.CharField(_("keyword"), max_length=16, blank=False, null=False)
    # Hex colour. #FFFFFF
    color = models.CharField(
        _("color"),
        max_length=COLOR_ATTR_MAX_LENGTH,
        blank=False,
        null=False,
        validators=[hex_color_validator],
        unique=False,
    )
    image = models.ImageField(_("image"), blank=False, null=False)
    created = models.DateTimeField(editable=False)
    order = models.IntegerField(unique=False, default=100)

    def __str__(self):
        return "Emoji: " + self.keyword

    def save(self, *args, **kwargs):
        """On save, update timestamps"""
        if not self.created:
            self.created = timezone.now()
        return super(Emoji, self).save(*args, **kwargs)


class Badge(ModelWithUUID):
    keyword = models.CharField(max_length=16, blank=False, null=False, unique=True)
    keyword_description = models.CharField(_("keyword_description"), max_length=64, blank=True, null=True, unique=True)
    created = models.DateTimeField(editable=False)

    def save(self, *args, **kwargs):
        if not self.created:
            self.created = timezone.now()
        return super(Badge, self).save(*args, **kwargs)


class Language(ModelWithUUID):
    code = models.CharField(_("code"), max_length=12, blank=False, null=False)
    name = models.CharField(_("name"), max_length=64, blank=False, null=False)
    created = models.DateTimeField(editable=False)

    def __str__(self):
        return "Language: " + self.code

    def save(self, *args, **kwargs):
        if not self.created:
            self.created = timezone.now()
        return super(Language, self).save(*args, **kwargs)


class ProxyBlacklistedDomain(ModelWithUUID):
    domain = models.CharField(max_length=settings.PROXY_BLACKLIST_DOMAIN_MAX_LENGTH, unique=True)

    @classmethod
    def is_url_domain_blacklisted(cls, url):
        url = url.lower()

        if not urlparse(url).scheme:
            url = "http://" + url

        # This uses a list of public suffixes
        tld_extract_result = tldextract.extract(url)

        # given test.blogspot.com

        # blogspot.com
        url_root_domain = ".".join([tld_extract_result.domain, tld_extract_result.suffix])

        # test.blogspot.com
        url_full_domain = ".".join(
            [
                tld_extract_result.subdomain,
                tld_extract_result.domain,
                tld_extract_result.suffix,
            ]
        )

        return cls.objects.filter(Q(domain=url_root_domain) | Q(domain=url_full_domain)).exists()


class LinkPreview(ModelWithUUID):
    requested_url = models.TextField(unique=True)
    url = models.TextField()
    title = models.TextField()
    description = models.TextField()
    type = models.TextField()
    image = models.TextField()
    site_name = models.TextField()
    icon = models.URLField(null=True, blank=True)
    fetched_at = models.DateTimeField(default=timezone.now, editable=False)

    fields = [
        "og:url",
        "og:title",
        "og:description",
        "og:type",
        "og:image",
        "og:site_name",
    ]

    @classmethod
    def parse_text(cls, text) -> List[LinkPreview]:
        previews = []
        link_urls = extract_urls_from_string(text)
        if link_urls:
            for link_url in link_urls:
                preview = cls.from_url(link_url)
                if preview.has_data():
                    previews.append(preview)
        return previews

    @classmethod
    def from_url(cls, url):
        normalized_url = normalize_url(url)
        preview, created = cls.objects.get_or_create(requested_url=normalized_url)
        if not created and preview.fetched_at > timezone.now() - timezone.timedelta(
            hours=settings.LINK_PREVIEW_CACHE_TIME_H
        ):
            return preview

        html = LinkPreview._fetch_html_of_url(normalized_url)
        og = cls.get_opengraph(html, url=normalized_url)
        preview.fetched_at = timezone.now()

        for field in cls.fields:
            value = og.get(field[3:])
            if value is not None:
                setattr(preview, field[3:], value)

        preview.icon = LinkPreview._fetch_icon(html, url=normalized_url)

        preview.save()
        return preview

    @staticmethod
    def _fetch_html_of_url(url: str) -> BeautifulSoup:
        response = requests.get(url=url)
        if hasattr(response, "apparent_encoding") and response.apparent_encoding:
            response.encoding = response.apparent_encoding
        else:
            response.encoding = "utf-8"  # Set to utf-8 by default if apparent_encoding is not found

        return BeautifulSoup(response.text, "html.parser")

    @classmethod
    def get_opengraph(cls, html: BeautifulSoup, url: str) -> dict[str, str]:
        og = {}
        try:
            for m in html.find_all("meta"):
                meta_property = m.get("property", None)
                if meta_property in cls.fields:
                    og[meta_property[3:]] = m.get("content", None)
            # sometimes image urls are relative, so use urljoin to prefix with og:url or url in those cases
            if og.get("image"):
                if og.get("url"):
                    og["image"] = urljoin(og["url"], og["image"])
                else:
                    og["image"] = urljoin(url, og["image"])

            if not og.get("title"):
                title = html.find("title")
                if title and title.string:
                    og["title"] = title.string
            return og
        except RequestException:
            return og

    @staticmethod
    def _fetch_icon(html: BeautifulSoup, url: str) -> str | None:
        icon = html.find("link", rel="icon")
        if icon is not None and "href" in icon.attrs:
            return urljoin(url, icon["href"])

        return None

    def has_data(self):
        return any(attr_filled(self, field[3:]) for field in self.fields)

    def get_origin(self):
        split = urlsplit(normalize_url(self.requested_url))
        return f"{split.scheme}://{split.netloc}"


class AppVersion(ModelWithUUID):
    version = models.CharField(max_length=16, blank=False, null=False)
    build_number = models.CharField(max_length=16, blank=True, null=True)
    need_update = models.CharField(
        max_length=12,
        choices=NeedUpdateType.choices,
        default=NeedUpdateType.NO,
        blank=False,
        null=False,
    )
    created = models.DateTimeField(default=timezone.now, editable=False)
    app_store_url = models.CharField(max_length=100, default=settings.APPLE_APP_STORE_DEFAULT_URL)
    play_store_url = models.CharField(max_length=100, default=settings.GOOGLE_PLAY_STORE_DEFAULT_URL)

    class Meta:
        unique_together = (
            "version",
            "build_number",
        )


class FeatureToggle(ModelWithUUID):
    name = models.CharField(max_length=50, unique=True, blank=False, null=False)
    created = models.DateTimeField(default=timezone.now, editable=False)
    status = models.CharField(
        max_length=20,
        choices=FeatureToggleType.choices,
        default=FeatureToggleType.OFF,
        blank=False,
        null=False,
    )
