"""
Pluggable caching: LRU/TTL memory backends, decorators, and shared managers.

Features:
- LRU in-memory cache
- TTL support
- Decorator-based caching
- Central stats and management
- Easy to extend (e.g. Redis)
"""

from .base import CacheManager, CacheBackend
from .memory import LRUCache, TTLCache
from .decorators import cacheable
from .config import CacheConfig
from .utils import normalize_query, generate_hash_key, create_cache_key_from_dict

__all__ = [
    'CacheManager', 'CacheBackend', 'LRUCache', 'TTLCache',
    'cacheable', 'CacheConfig',
    'normalize_query', 'generate_hash_key', 'create_cache_key_from_dict'
]


def initialize_cache(config=None):
    """
    Initialize cache subsystems.

    Args:
        config: Optional cache config dict; uses defaults when None.
    """
    CacheConfig.initialize_caches(config)


initialize_cache()
