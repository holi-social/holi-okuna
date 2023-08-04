import hashlib
from django.core.cache import caches

from openbook.settings import UNIFIED_API_RESPONSE_CACHE

SUPPORTED_EMAIL_LANGUAGES = ["DE", "EN"]
DEFAULT_EMAIL_LANGUAGE = "DE"


def unified_api_response_cache_key_function(key: str, key_prefix: str, version: int | None = None) -> str:
    return ":".join([key_prefix, key])


def unified_api_response_cache_reverse_key(key: str) -> str:
    return key.split(":", 1)[1]


# Clears the cache entries of discover_spaces query
def invalidate_discover_spaces_query_cache():
    # clean unified api response caching
    unified_api_cache = caches[UNIFIED_API_RESPONSE_CACHE]
    unified_api_cache.delete_many(unified_api_cache.keys("DiscoverSpaces-*"))


# Generates a unique SHA-256 hash for any given string
def generate_hash(value: str):
    utf8_encoded = value.encode("utf-8")
    return hashlib.sha256(utf8_encoded).hexdigest()


# Supported languages for emails are only German or English
def get_supported_language_for_email(language: str):
    lang = (language or DEFAULT_EMAIL_LANGUAGE).split("-")[0].upper()
    if lang in SUPPORTED_EMAIL_LANGUAGES:
        return lang
    return DEFAULT_EMAIL_LANGUAGE
