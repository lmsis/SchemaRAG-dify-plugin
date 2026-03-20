"""
Abstract cache backend and named CacheManager facade.
"""

from abc import ABC, abstractmethod
from typing import Any, Dict, Optional, Generic, TypeVar
import logging

K = TypeVar('K')
V = TypeVar('V')


class CacheBackend(ABC, Generic[K, V]):
    """Pluggable cache storage API."""

    @abstractmethod
    def get(self, key: K) -> Optional[V]:
        """Return value or None if missing/expired."""
        pass

    @abstractmethod
    def set(self, key: K, value: V, ttl: Optional[int] = None) -> None:
        """Store value; ttl in seconds, None = no expiry."""
        pass

    @abstractmethod
    def delete(self, key: K) -> bool:
        """Delete entry; return whether it existed."""
        pass

    @abstractmethod
    def clear(self) -> None:
        """Remove all entries."""
        pass

    @abstractmethod
    def get_stats(self) -> Dict[str, Any]:
        """Backend-specific counters."""
        pass


class CacheManager:
    """
    Named cache facade with hit/miss counters.

    Multiple named instances; each can use a different backend.
    """

    _instances: Dict[str, 'CacheManager'] = {}
    _logger = logging.getLogger(__name__)

    @classmethod
    def get_instance(cls, name: str = "default") -> 'CacheManager':
        """Get or create a named manager."""
        if name not in cls._instances:
            from .memory import LRUCache
            cls._instances[name] = CacheManager(name)
            cls._instances[name].set_backend(LRUCache(max_size=100))
            cls._logger.info(f"Created cache manager '{name}' with default LRU backend")
        return cls._instances[name]

    @classmethod
    def get_all_instances(cls) -> Dict[str, 'CacheManager']:
        """Snapshot of all managers."""
        return cls._instances.copy()

    def __init__(self, name: str):
        self.name = name
        self._backend: Optional[CacheBackend] = None
        self.hit_count = 0
        self.miss_count = 0

    def set_backend(self, backend: CacheBackend) -> None:
        """Attach a backend implementation."""
        self._backend = backend
        self._logger.info(f"Cache manager '{self.name}' backend: {backend.__class__.__name__}")

    def get(self, key: Any) -> Optional[Any]:
        """Get through backend and update hit/miss stats."""
        if not self._backend:
            self._logger.warning(f"Cache manager '{self.name}' has no backend")
            return None

        result = self._backend.get(key)
        if result is not None:
            self.hit_count += 1
            self._logger.debug(f"Cache hit: {self.name}:{key}")
        else:
            self.miss_count += 1
            self._logger.debug(f"Cache miss: {self.name}:{key}")

        return result

    def set(self, key: Any, value: Any, ttl: Optional[int] = None) -> None:
        """Set through backend."""
        if self._backend:
            self._backend.set(key, value, ttl)
            self._logger.debug(f"Cache set: {self.name}:{key}, TTL={ttl}")
        else:
            self._logger.warning(f"Cache manager '{self.name}' has no backend; cannot set")

    def delete(self, key: Any) -> bool:
        """Delete through backend."""
        if self._backend:
            result = self._backend.delete(key)
            if result:
                self._logger.debug(f"Cache delete: {self.name}:{key}")
            return result
        return False

    def clear(self) -> None:
        """Clear backend contents."""
        if self._backend:
            self._backend.clear()
            self._logger.info(f"Cache cleared: {self.name}")

    def get_stats(self) -> Dict[str, Any]:
        """Hit rate plus backend stats."""
        total = self.hit_count + self.miss_count
        hit_rate = self.hit_count / total if total > 0 else 0

        stats = {
            "name": self.name,
            "hit_count": self.hit_count,
            "miss_count": self.miss_count,
            "total_requests": total,
            "hit_rate": round(hit_rate * 100, 2)
        }

        if self._backend:
            stats.update(self._backend.get_stats())

        return stats

    def reset_stats(self) -> None:
        """Zero hit/miss counters."""
        self.hit_count = 0
        self.miss_count = 0
        self._logger.info(f"Cache stats reset: {self.name}")
