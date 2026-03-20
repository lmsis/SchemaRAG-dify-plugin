"""
Context storage backends (pluggable).
"""

import abc
import threading
from typing import Dict, Optional
from datetime import datetime, timedelta
from .models import UserContext


class ContextStorage(abc.ABC):
    """Abstract base class for context storage."""

    @abc.abstractmethod
    def get_context(self, context_key: str) -> Optional[UserContext]:
        """Load context by key."""
        pass

    @abc.abstractmethod
    def save_context(self, user_context: UserContext) -> bool:
        """Persist user context."""
        pass

    @abc.abstractmethod
    def delete_context(self, context_key: str) -> bool:
        """Delete context by key."""
        pass

    @abc.abstractmethod
    def cleanup_expired(self, max_age_seconds: int) -> int:
        """Remove contexts older than max_age_seconds; return count removed."""
        pass


class MemoryContextStorage(ContextStorage):
    """In-memory context storage."""

    def __init__(self):
        self._contexts: Dict[str, UserContext] = {}
        self._lock = threading.RLock()
        self._last_cleanup = datetime.now()

    def get_context(self, context_key: str) -> Optional[UserContext]:
        """Get user context and bump last_access."""
        with self._lock:
            context = self._contexts.get(context_key)
            if context:
                context.last_access = datetime.now()
            return context

    def save_context(self, user_context: UserContext) -> bool:
        """Save user context."""
        with self._lock:
            self._contexts[user_context.context_key] = user_context
            return True

    def delete_context(self, context_key: str) -> bool:
        """Delete one context."""
        with self._lock:
            if context_key in self._contexts:
                del self._contexts[context_key]
                return True
            return False

    def cleanup_expired(self, max_age_seconds: int) -> int:
        """Drop contexts whose last_access is older than the cutoff."""
        cutoff_time = datetime.now() - timedelta(seconds=max_age_seconds)
        expired_count = 0

        with self._lock:
            expired_keys = [
                key for key, context in self._contexts.items()
                if context.last_access < cutoff_time
            ]

            for key in expired_keys:
                del self._contexts[key]
                expired_count += 1

        return expired_count

    def get_stats(self) -> Dict[str, int]:
        """Return simple storage counters."""
        with self._lock:
            total_conversations = sum(
                len(ctx.conversations) for ctx in self._contexts.values()
            )
            return {
                "total_contexts": len(self._contexts),
                "total_conversations": total_conversations
            }
