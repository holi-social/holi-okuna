from django.core.cache import caches
from django.db.models import Model
from django.db.models.signals import post_delete, post_save
from django.dispatch import receiver

from openbook.settings import UNIFIED_API_RESPONSE_CACHE
from openbook.utils import invalidate_discover_spaces_query_cache
from openbook_communities.models import Community


@receiver(post_save, sender=Community)
def invalidate_discover_spaces_response_cache(sender: Model, instance: Community, **kwargs) -> None:
    # clean unified api response caching
    cache = caches[UNIFIED_API_RESPONSE_CACHE]
    cache.delete_many(cache.keys("DiscoverSpaces-*"))

    invalidate_discover_spaces_query_cache()


@receiver(post_delete, sender=Community)
def invalidate_discover_spaces_response_cache(sender: Model, instance: Community, **kwargs) -> None:
    # clean unified api response caching
    cache = caches[UNIFIED_API_RESPONSE_CACHE]
    cache.delete_many(cache.keys("DiscoverSpaces-*"))

    invalidate_discover_spaces_query_cache()
