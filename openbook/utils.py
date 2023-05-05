import hashlib
from django.core.cache import cache

DISCOVER_SPACES_CACHE_KEY_PREFIX = "discover_spaces"

# Generates a unique cache key consisting of DISCOVER_SPACES_CACHE_KEY_PREFIX and SHA-256 hash of the discover spaces filters
# e.g discover_spaces:2cbce4f20876d36947b2db0d6b229c8b2b80741434ceca8e7e3f2258114c2511
def generate_discover_spaces_hash_key(topic_ids, geolocation, skill_ids, offset, limit):
    key_parts = []

    if geolocation is not None:
        key_parts.append(str(geolocation.id))

    if topic_ids is not None:
        key_parts.extend([str(topic_id) for topic_id in topic_ids])

    if skill_ids is not None:
        key_parts.extend([str(skill_id) for skill_id in skill_ids])

    if offset is not None:
        key_parts.append(str(offset))

    if limit is not None:
        key_parts.append(str(limit))

    key = "_".join(key_parts)

    key_hash = hashlib.sha256(key.encode()).hexdigest()
    return f"{DISCOVER_SPACES_CACHE_KEY_PREFIX}:{key_hash}"


# Clears the cache entries of discover_spaces query
def invalidate_discover_spaces_query_cache():
    all_keys = cache.keys("*")
    filtered_keys = [key for key in all_keys if key.startswith(DISCOVER_SPACES_CACHE_KEY_PREFIX)]
    cache.delete_many(filtered_keys)
