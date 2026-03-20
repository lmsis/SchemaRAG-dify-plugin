"""
High-level context manager for tools.
"""

from typing import Dict, List, Optional, Any
from datetime import datetime, timedelta
import logging
import uuid

from .models import UserContext, Conversation
from .storage import ContextStorage, MemoryContextStorage


class ContextManager:
    """Coordinates context load/save and retention."""

    DEFAULT_MEMORY_WINDOW = 3         # recent turns kept for prompts
    DEFAULT_EXPIRY_TIME = 24 * 3600   # seconds (24h)
    CLEANUP_INTERVAL = 3600           # run cleanup at most every hour

    _shared_storage: Optional[ContextStorage] = None

    def __init__(self, storage: Optional[ContextStorage] = None):
        """
        Args:
            storage: Optional custom backend; defaults to shared in-memory store.
        """
        if storage is None:
            if ContextManager._shared_storage is None:
                ContextManager._shared_storage = MemoryContextStorage()
            self.storage = ContextManager._shared_storage
        else:
            self.storage = storage

        self.logger = logging.getLogger(__name__)
        self._last_cleanup = datetime.now()

    def _auto_cleanup(self) -> None:
        """Periodically drop expired contexts."""
        now = datetime.now()
        if now - self._last_cleanup > timedelta(seconds=self.CLEANUP_INTERVAL):
            self._last_cleanup = now
            try:
                cleaned = self.storage.cleanup_expired(self.DEFAULT_EXPIRY_TIME)
                if cleaned > 0:
                    self.logger.info(f"Cleaned up {cleaned} expired context(s)")
            except Exception as e:
                self.logger.error(f"Context cleanup error: {e}")

    def _get_user_id(self, user_id: Optional[str] = None) -> str:
        """Resolve or mint user id."""
        if user_id:
            return user_id
        return f"anon_{uuid.uuid4().hex[:8]}"

    def get_context(self, user_id: Optional[str] = None, tool_name: str = "text2sql") -> UserContext:
        """
        Load or create user context.

        Args:
            user_id: Optional explicit user id (anonymous if omitted)
            tool_name: Tool namespace for the context key

        Returns:
            UserContext instance
        """
        self._auto_cleanup()

        user_id = self._get_user_id(user_id)
        context_key = f"{user_id}:{tool_name}"
        user_context = self.storage.get_context(context_key)

        if not user_context:
            user_context = UserContext(user_id=user_id, tool_name=tool_name)
            self.storage.save_context(user_context)

        return user_context

    def add_conversation(
        self,
        query: str,
        sql: str,
        user_id: Optional[str] = None,
        tool_name: str = "text2sql",
        metadata: Optional[Dict[str, Any]] = None
    ) -> None:
        """
        Append one query/SQL turn.

        Args:
            query: User question
            sql: Generated SQL
            user_id: Optional user id
            tool_name: Defaults to text2sql
            metadata: Extra fields
        """
        try:
            user_context = self.get_context(user_id, tool_name)
            conversation = Conversation(
                query=query,
                sql=sql,
                metadata=metadata or {}
            )
            user_context.add_conversation(conversation)
            self.storage.save_context(user_context)

            self.logger.debug(f"Recorded conversation for user: {user_id}")
        except Exception as e:
            self.logger.error(f"add_conversation failed: {e}")

    def get_conversation_history(
        self,
        user_id: Optional[str] = None,
        tool_name: str = "text2sql",
        window_size: int = DEFAULT_MEMORY_WINDOW
    ) -> List[Dict[str, Any]]:
        """
        Recent turns as dicts.

        Args:
            user_id: Optional user id
            tool_name: Tool name
            window_size: Max turns to return

        Returns:
            List of serialized Conversation dicts
        """
        try:
            user_context = self.get_context(user_id, tool_name)
            recent_conversations = user_context.get_recent_conversations(window_size)
            return [conv.to_dict() for conv in recent_conversations]
        except Exception as e:
            self.logger.error(f"get_conversation_history failed: {e}")
            return []

    def reset_memory(
        self,
        user_id: Optional[str] = None,
        tool_name: str = "text2sql"
    ) -> bool:
        """
        Clear stored turns for the user/tool.

        Returns:
            True if save succeeded
        """
        try:
            user_id = self._get_user_id(user_id)
            user_context = self.get_context(user_id, tool_name)
            user_context.clear_conversations()
            success = self.storage.save_context(user_context)

            if success:
                self.logger.info(f"Reset memory for user: {user_id}")

            return success
        except Exception as e:
            self.logger.error(f"reset_memory failed: {e}")
            return False

    def get_storage_stats(self) -> Dict[str, int]:
        """Optional stats from storage backend."""
        if hasattr(self.storage, 'get_stats'):
            return self.storage.get_stats()
        return {}
