"""
Data models for conversation and user context.
"""

from datetime import datetime
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field


@dataclass
class Conversation:
    """One turn: user query and generated SQL."""

    query: str  # user question
    sql: str    # generated SQL
    timestamp: datetime = field(default_factory=datetime.now)
    metadata: Dict[str, Any] = field(default_factory=dict)  # e.g. dialect, schema hints

    def to_dict(self) -> Dict[str, Any]:
        """Serialize to a dict."""
        return {
            "query": self.query,
            "sql": self.sql,
            "timestamp": self.timestamp.timestamp(),
            "metadata": self.metadata
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Conversation":
        """Deserialize from dict."""
        ts = data.get("timestamp")
        if isinstance(ts, (int, float)):
            timestamp = datetime.fromtimestamp(ts)
        else:
            timestamp = datetime.now()

        return cls(
            query=data.get("query", ""),
            sql=data.get("sql", ""),
            timestamp=timestamp,
            metadata=data.get("metadata", {})
        )


@dataclass
class UserContext:
    """Per-user, per-tool conversation buffer."""

    user_id: str
    tool_name: str = "text2sql"
    conversations: List[Conversation] = field(default_factory=list)
    created_at: datetime = field(default_factory=datetime.now)
    last_access: datetime = field(default_factory=datetime.now)

    @property
    def context_key(self) -> str:
        """Stable storage key."""
        return f"{self.user_id}:{self.tool_name}"

    def add_conversation(self, conversation: Conversation) -> None:
        """Append a turn."""
        self.conversations.append(conversation)
        self.last_access = datetime.now()

    def get_recent_conversations(self, window_size: int) -> List[Conversation]:
        """Last `window_size` turns."""
        return self.conversations[-min(window_size, len(self.conversations)):]

    def clear_conversations(self) -> None:
        """Drop all turns."""
        self.conversations = []
        self.last_access = datetime.now()

    def to_dict(self) -> Dict[str, Any]:
        """Serialize to dict."""
        return {
            "user_id": self.user_id,
            "tool_name": self.tool_name,
            "conversations": [conv.to_dict() for conv in self.conversations],
            "created_at": self.created_at.timestamp(),
            "last_access": self.last_access.timestamp()
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "UserContext":
        """Deserialize from dict."""
        user_context = cls(
            user_id=data.get("user_id", ""),
            tool_name=data.get("tool_name", "text2sql")
        )

        created_ts = data.get("created_at")
        if isinstance(created_ts, (int, float)):
            user_context.created_at = datetime.fromtimestamp(created_ts)

        access_ts = data.get("last_access")
        if isinstance(access_ts, (int, float)):
            user_context.last_access = datetime.fromtimestamp(access_ts)

        for conv_data in data.get("conversations", []):
            user_context.conversations.append(Conversation.from_dict(conv_data))

        return user_context
