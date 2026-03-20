"""
Bootstrap and introspection for named caches.
"""

from typing import Any, Dict, Optional
import logging

from .base import CacheManager
from .memory import LRUCache, TTLCache


class CacheConfig:
    """Register backends for each named CacheManager."""

    DEFAULT_CONFIG = {
        "schema_cache": {
            "type": "lru",
            "max_size": 100,
            "ttl": 3600
        },
        "sql_cache": {
            "type": "lru",
            "max_size": 50,
            "ttl": 7200
        },
        "prompt_cache": {
            "type": "lru",
            "max_size": 20,
            "ttl": 86400
        },
        "dataset_info_cache": {
            "type": "ttl",
            "max_size": 50,
            "default_ttl": 3600
        }
    }

    _logger = logging.getLogger(__name__)
    _initialized = False

    @classmethod
    def initialize_caches(cls, config: Optional[Dict[str, Any]] = None) -> None:
        if cls._initialized:
            cls._logger.info("Cache system already initialized; skipping")
            return

        if config is None:
            config = cls.DEFAULT_CONFIG
            cls._logger.info("Using default cache configuration")

        cls._logger.info(f"Initializing {len(config)} cache instance(s)")

        for cache_name, cache_config in config.items():
            try:
                cls._initialize_single_cache(cache_name, cache_config)
            except Exception as e:
                cls._logger.error(f"Failed to init cache '{cache_name}': {e}")

        cls._initialized = True
        cls._logger.info("Cache system initialization complete")

    @classmethod
    def _initialize_single_cache(cls, cache_name: str, cache_config: Dict[str, Any]) -> None:
        cache_type = cache_config.get("type", "lru")
        max_size = cache_config.get("max_size", 100)

        cache_manager = CacheManager.get_instance(cache_name)

        if cache_type == "lru":
            backend = LRUCache(max_size=max_size)
        elif cache_type == "ttl":
            default_ttl = cache_config.get("default_ttl", 3600)
            backend = TTLCache(max_size=max_size, default_ttl=default_ttl)
        else:
            cls._logger.warning(f"Unknown cache type '{cache_type}'; using LRU")
            backend = LRUCache(max_size=max_size)

        cache_manager.set_backend(backend)
        cls._logger.info(
            f"Cache '{cache_name}' ready: type={cache_type}, max_size={max_size}"
        )

    @classmethod
    def get_all_stats(cls) -> Dict[str, Dict[str, Any]]:
        stats = {}
        all_instances = CacheManager.get_all_instances()

        for cache_name, cache_manager in all_instances.items():
            try:
                stats[cache_name] = cache_manager.get_stats()
            except Exception as e:
                cls._logger.error(f"Stats failed for '{cache_name}': {e}")
                stats[cache_name] = {"error": str(e)}

        return stats

    @classmethod
    def clear_all_caches(cls) -> None:
        cls._logger.info("Clearing all caches")
        all_instances = CacheManager.get_all_instances()

        for cache_name, cache_manager in all_instances.items():
            try:
                cache_manager.clear()
                cls._logger.info(f"Cleared cache: {cache_name}")
            except Exception as e:
                cls._logger.error(f"Clear failed for '{cache_name}': {e}")

    @classmethod
    def reset_all_stats(cls) -> None:
        cls._logger.info("Resetting all cache statistics")
        all_instances = CacheManager.get_all_instances()

        for cache_name, cache_manager in all_instances.items():
            try:
                cache_manager.reset_stats()
            except Exception as e:
                cls._logger.error(f"Stats reset failed for '{cache_name}': {e}")

    @classmethod
    def get_cache(cls, name: str) -> CacheManager:
        return CacheManager.get_instance(name)

    @classmethod
    def update_cache_config(cls, cache_name: str, config: Dict[str, Any]) -> None:
        cls._logger.info(f"Updating cache config: {cache_name}")
        cls._initialize_single_cache(cache_name, config)

    @classmethod
    def is_initialized(cls) -> bool:
        return cls._initialized

    @classmethod
    def get_summary(cls) -> Dict[str, Any]:
        all_stats = cls.get_all_stats()

        total_caches = len(all_stats)
        total_items = sum(
            stats.get("current_size", 0)
            for stats in all_stats.values()
        )
        total_hits = sum(
            stats.get("hit_count", 0)
            for stats in all_stats.values()
        )
        total_misses = sum(
            stats.get("miss_count", 0)
            for stats in all_stats.values()
        )
        total_requests = total_hits + total_misses
        overall_hit_rate = (
            round(total_hits / total_requests * 100, 2)
            if total_requests > 0
            else 0
        )

        return {
            "initialized": cls._initialized,
            "total_caches": total_caches,
            "total_cached_items": total_items,
            "total_requests": total_requests,
            "total_hits": total_hits,
            "total_misses": total_misses,
            "overall_hit_rate": overall_hit_rate,
            "caches": list(all_stats.keys())
        }
