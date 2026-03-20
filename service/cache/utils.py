"""
Helpers for cache keys and query normalization.
"""

import re
import hashlib
from typing import Any, List


def normalize_query(query: str, remove_stopwords: bool = True) -> str:
    """
    Normalize a query string to improve cache hit rate.

    Args:
        query: Raw query text
        remove_stopwords: If True, strip common filler tokens (see stopword list)

    Returns:
        Normalized string

    Examples:
        >>> normalize_query("  please   help  find user info  ")
        'please help find user info'
        >>> normalize_query("SELECT * FROM users", remove_stopwords=False)
        'select * from users'
    """
    if not query or not isinstance(query, str):
        return ""

    normalized = re.sub(r'\s+', ' ', query).lower().strip()

    if remove_stopwords:
        # Common Chinese NL fillers (kept for zh query normalization)
        stopwords = [
            "请", "帮我", "查询", "获取", "告诉我", "我想",
            "能否", "可以", "如何", "怎么", "帮忙"
        ]
        for word in stopwords:
            normalized = normalized.replace(word, "")

        normalized = re.sub(r'\s+', ' ', normalized).strip()

    return normalized


def generate_hash_key(*args: Any, **kwargs: Any) -> str:
    """
    MD5 over serialized args/kwargs for stable cache keys.

    Returns:
        32-char hex digest
    """
    args_str = str(args)
    kwargs_str = str(sorted(kwargs.items()))
    combined = args_str + kwargs_str

    return hashlib.md5(combined.encode('utf-8')).hexdigest()


def generate_cache_key(prefix: str, *args: Any, **kwargs: Any) -> str:
    """Return ``prefix:hash``."""
    hash_key = generate_hash_key(*args, **kwargs)
    return f"{prefix}:{hash_key}"


def create_cache_key_from_dict(prefix: str, params: dict) -> str:
    """Build a key from a sorted dict view."""
    sorted_items = sorted(params.items())
    combined = str(sorted_items)
    hash_key = hashlib.md5(combined.encode('utf-8')).hexdigest()
    return f"{prefix}:{hash_key}"


def sanitize_cache_key(key: str, max_length: int = 250) -> str:
    """Sanitize key characters and cap length (hash middle if needed)."""
    sanitized = re.sub(r'[^\w\-:]', '_', key)

    if len(sanitized) > max_length:
        prefix_len = min(50, max_length // 3)
        suffix_len = min(50, max_length // 3)

        prefix = sanitized[:prefix_len]
        suffix = sanitized[-suffix_len:]
        middle_hash = hashlib.md5(sanitized.encode('utf-8')).hexdigest()[:16]

        sanitized = f"{prefix}_{middle_hash}_{suffix}"

    return sanitized


def estimate_string_size(text: str) -> int:
    """Approximate UTF-8 byte size of a string."""
    try:
        return len(text.encode('utf-8'))
    except Exception:
        return len(text) * 2


def batch_normalize_queries(queries: List[str]) -> List[str]:
    """Apply normalize_query to each entry."""
    return [normalize_query(q) for q in queries]


def is_cache_key_valid(key: Any) -> bool:
    """True if key is hashable (and not None)."""
    if key is None:
        return False

    try:
        hash(key)
        return True
    except TypeError:
        return False
