from django.test import TestCase
from django.core.cache import cache

from openbook.utils import (
    DISCOVER_SPACES_CACHE_KEY_PREFIX,
    generate_discover_spaces_hash_key,
    invalidate_discover_spaces_query_cache,
)
from openbook_common.tests.helpers import make_skill, make_topic
from openbook_common.types import GeolocationFeature


class DiscoverSpacesQueryCacheTest(TestCase):
    def test_invalidate_discover_spaces_query_cache(self):
        topic_ids = [str(make_topic().id) for _ in range(3)]
        geolocation = GeolocationFeature(id="123")
        skill_ids = [str(make_skill().id) for _ in range(3)]
        result = []

        other_topic_ids = [str(make_topic().id) for _ in range(3)]
        other_geolocation = GeolocationFeature(id="234")
        other_skill_ids = [str(make_skill().id) for _ in range(3)]
        other_result = []

        hash_key = generate_discover_spaces_hash_key(topic_ids, geolocation, skill_ids, 0, 10)
        other_hash_key = generate_discover_spaces_hash_key(other_topic_ids, other_geolocation, other_skill_ids, 0, 10)

        # Set up the cache
        cache.set(hash_key, result)
        cache.set(other_hash_key, other_result)
        cache.set("key", "value")

        # Check that the cache has the expected keys
        self.assertIn(hash_key, cache)
        self.assertIn(other_hash_key, cache)
        self.assertIn("key", cache)

        # Call the function to invalidate the cache entries
        invalidate_discover_spaces_query_cache()

        # Check that only the cache entries with of discover_spaces query have been removed
        self.assertNotIn(hash_key, cache)
        self.assertNotIn(other_hash_key, cache)
        self.assertIn("key", cache)
