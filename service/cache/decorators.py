"""
Caching decorators built on CacheManager.
"""

import functools
from typing import Any, Callable, Optional
import logging

from .base import CacheManager
from .utils import generate_cache_key


def cacheable(
    name: str = "default",
    key_prefix: str = "",
    ttl: Optional[int] = None,
    key_generator: Optional[Callable] = None,
    condition: Optional[Callable] = None
):
    """
    Memoize function results in a named cache.

    Args:
        name: CacheManager instance name
        key_prefix: Key prefix (defaults to function name)
        ttl: TTL seconds; None uses backend default
        key_generator: Optional callable(args, kwargs) -> str key
        condition: If set, only cache when condition(result) is True
    """
    logger = logging.getLogger(__name__)

    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            cache_manager = CacheManager.get_instance(name)

            if key_generator:
                try:
                    cache_key = key_generator(*args, **kwargs)
                except Exception as e:
                    logger.warning(f"Custom key generator failed: {e}; using default key")
                    cache_key = generate_cache_key(
                        key_prefix or func.__name__,
                        *args,
                        **kwargs
                    )
            else:
                cache_key = generate_cache_key(
                    key_prefix or func.__name__,
                    *args,
                    **kwargs
                )

            cached_result = cache_manager.get(cache_key)
            if cached_result is not None:
                logger.debug(f"Cache hit: {func.__name__}, key={cache_key}")
                return cached_result

            logger.debug(f"Cache miss: {func.__name__}")
            result = func(*args, **kwargs)

            should_cache = True
            if condition is not None:
                try:
                    should_cache = condition(result)
                except Exception as e:
                    logger.warning(f"Cache condition failed: {e}; caching anyway")

            if should_cache:
                cache_manager.set(cache_key, result, ttl)
                logger.debug(f"Cache store: {func.__name__}, key={cache_key}")

            return result

        wrapper.cache_clear = lambda: CacheManager.get_instance(name).clear()
        wrapper.cache_info = lambda: CacheManager.get_instance(name).get_stats()

        return wrapper

    return decorator


def cache_result(
    cache_manager_name: str,
    ttl: Optional[int] = None,
    key_func: Optional[Callable] = None
):
    """Shorthand for cacheable with a named manager."""
    return cacheable(
        name=cache_manager_name,
        ttl=ttl,
        key_generator=key_func
    )


def invalidate_cache(cache_manager_name: str, key: Optional[Any] = None):
    """
    After the wrapped function runs, clear one key or the whole cache.

    Args:
        cache_manager_name: Manager name
        key: Entry to delete; None clears all
    """
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            result = func(*args, **kwargs)

            cache_manager = CacheManager.get_instance(cache_manager_name)
            if key is None:
                cache_manager.clear()
            else:
                cache_manager.delete(key)

            return result
        return wrapper
    return decorator


class CachedProperty:
    """Lazy per-instance cached attribute."""

    def __init__(self, func: Callable):
        self.func = func
        self.attr_name = f"_cached_{func.__name__}"
        functools.update_wrapper(self, func)

    def __get__(self, instance, owner):
        if instance is None:
            return self

        if not hasattr(instance, self.attr_name):
            result = self.func(instance)
            setattr(instance, self.attr_name, result)

        return getattr(instance, self.attr_name)

    def __set__(self, instance, value):
        setattr(instance, self.attr_name, value)

    def __delete__(self, instance):
        if hasattr(instance, self.attr_name):
            delattr(instance, self.attr_name)
