"""
In-memory LRU and fixed-TTL cache backends.
"""

import time
from typing import Any, Dict, Optional, Tuple
from collections import OrderedDict
import logging

from .base import CacheBackend


class LRUCache(CacheBackend):
    """
    LRU eviction using OrderedDict; per-entry optional TTL.

    Stored tuple: (value, expire_time or None)
    """

    def __init__(self, max_size: int = 100):
        if max_size <= 0:
            raise ValueError("max_size must be positive")

        self.max_size = max_size
        self.cache: OrderedDict[Any, Tuple[Any, Optional[float]]] = OrderedDict()
        self._logger = logging.getLogger(__name__)

        self._logger.info(f"LRU cache init, max_size={max_size}")

    def get(self, key: Any) -> Optional[Any]:
        if key not in self.cache:
            return None

        value, expire_time = self.cache[key]

        if expire_time is not None and time.time() >= expire_time:
            self.delete(key)
            self._logger.debug(f"Cache entry expired: {key}")
            return None

        self.cache.move_to_end(key)
        return value

    def set(self, key: Any, value: Any, ttl: Optional[int] = None) -> None:
        expire_time = None if ttl is None else time.time() + ttl

        if key in self.cache:
            self.cache[key] = (value, expire_time)
            self.cache.move_to_end(key)
            self._logger.debug(f"Cache update: {key}")
            return

        if len(self.cache) >= self.max_size:
            oldest_key = next(iter(self.cache))
            self.delete(oldest_key)
            self._logger.debug(f"Cache full; evicted LRU key: {oldest_key}")

        self.cache[key] = (value, expire_time)
        self.cache.move_to_end(key)
        self._logger.debug(f"Cache insert: {key}, TTL={ttl}")

    def delete(self, key: Any) -> bool:
        if key in self.cache:
            del self.cache[key]
            self._logger.debug(f"Cache delete: {key}")
            return True
        return False

    def clear(self) -> None:
        count = len(self.cache)
        self.cache.clear()
        self._logger.info(f"Cache cleared, removed {count} entries")

    def get_stats(self) -> Dict[str, Any]:
        current_time = time.time()
        valid_items = 0
        expired_items = 0

        for value, expire_time in self.cache.values():
            if expire_time is None or expire_time > current_time:
                valid_items += 1
            else:
                expired_items += 1

        memory_estimate = sum(
            self._estimate_size(key) + self._estimate_size(value)
            for key, (value, _) in self.cache.items()
        )

        return {
            "backend_type": "lru_memory",
            "max_size": self.max_size,
            "current_size": len(self.cache),
            "valid_items": valid_items,
            "expired_items": expired_items,
            "usage_ratio": round(len(self.cache) / self.max_size * 100, 2),
            "memory_estimate_bytes": memory_estimate
        }

    def _estimate_size(self, obj: Any) -> int:
        try:
            import sys
            return sys.getsizeof(obj)
        except Exception:
            return 128

    def cleanup_expired(self) -> int:
        current_time = time.time()
        expired_keys = [
            key for key, (_, expire_time) in self.cache.items()
            if expire_time is not None and expire_time <= current_time
        ]

        for key in expired_keys:
            self.delete(key)

        if expired_keys:
            self._logger.info(f"Removed {len(expired_keys)} expired cache entries")

        return len(expired_keys)


class TTLCache(CacheBackend):
    """Simple dict cache with uniform default TTL per entry."""

    def __init__(self, max_size: int = 100, default_ttl: int = 3600):
        self.max_size = max_size
        self.default_ttl = default_ttl
        self.cache: Dict[Any, Tuple[Any, float]] = {}
        self._logger = logging.getLogger(__name__)

        self._logger.info(f"TTL cache init, max_size={max_size}, default_ttl={default_ttl}s")

    def get(self, key: Any) -> Optional[Any]:
        if key not in self.cache:
            return None

        value, expire_time = self.cache[key]

        if time.time() >= expire_time:
            self.delete(key)
            return None

        return value

    def set(self, key: Any, value: Any, ttl: Optional[int] = None) -> None:
        if ttl is None:
            ttl = self.default_ttl

        expire_time = time.time() + ttl

        if len(self.cache) >= self.max_size and key not in self.cache:
            for k, (_, exp_time) in list(self.cache.items()):
                if time.time() >= exp_time:
                    self.delete(k)
                    break
            else:
                first_key = next(iter(self.cache))
                self.delete(first_key)

        self.cache[key] = (value, expire_time)

    def delete(self, key: Any) -> bool:
        if key in self.cache:
            del self.cache[key]
            return True
        return False

    def clear(self) -> None:
        self.cache.clear()

    def get_stats(self) -> Dict[str, Any]:
        current_time = time.time()
        valid_items = sum(
            1 for _, expire_time in self.cache.values()
            if expire_time > current_time
        )

        return {
            "backend_type": "ttl_memory",
            "max_size": self.max_size,
            "current_size": len(self.cache),
            "valid_items": valid_items,
            "default_ttl": self.default_ttl
        }
