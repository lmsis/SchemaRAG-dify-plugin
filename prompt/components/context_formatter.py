"""
Format conversation history for prompts.
"""

from typing import List, Dict, Any, Optional


class ContextFormatter:
    """Turn stored turns into plain-text or chat-style snippets."""

    @staticmethod
    def format_conversation_history(
        conversation_history: List[Dict[str, Any]],
        max_length: Optional[int] = None
    ) -> str:
        """
        Flatten history into labeled lines for injection into a prompt.

        Args:
            conversation_history: List of dicts with query/sql
            max_length: Optional per-field truncation

        Returns:
            Single string block
        """
        if not conversation_history:
            return ""

        history_items = []
        for i, conv in enumerate(conversation_history, 1):
            query = conv.get('query', '')
            sql = conv.get('sql', '')

            if max_length:
                if len(query) > max_length:
                    query = query[:max_length] + "..."
                if len(sql) > max_length:
                    sql = sql[:max_length] + "..."

            history_items.append(f"Question {i}: {query}\nSQL {i}: {sql}")

        return "\n\n".join(history_items)

    @staticmethod
    def format_for_llm(conversation_history: List[Dict[str, Any]]) -> List[Dict[str, str]]:
        """
        Alternate shape: alternating user/assistant messages.

        Args:
            conversation_history: Same structure as above

        Returns:
            List of {role, content} dicts
        """
        messages = []
        for conv in conversation_history:
            messages.append({
                "role": "user",
                "content": conv.get('query', '')
            })
            messages.append({
                "role": "assistant",
                "content": conv.get('sql', '')
            })
        return messages

    @staticmethod
    def should_include_context(
        conversation_history: List[Dict[str, Any]],
        current_query: str
    ) -> bool:
        """
        Heuristic: include history when the query looks anaphoric.

        Args:
            conversation_history: Prior turns
            current_query: Latest user text

        Returns:
            True if history should be attached
        """
        if not conversation_history:
            return False

        # Chinese + English cue words for follow-ups
        reference_keywords = [
            '它', '这', '那', '上面', '上述', '刚才', '之前', '前面',
            '这个', '那个', '这些', '那些', '同样', '也', '还',
            'it', 'this', 'that', 'above', 'previous', 'same', 'also'
        ]

        query_lower = current_query.lower()
        for keyword in reference_keywords:
            if keyword in query_lower:
                return True

        return False
