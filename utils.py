"""
Utility module.
"""

import logging
from typing import Optional, Any, Dict, List
from collections import OrderedDict
import hashlib
from config import LoggerConfig

import datetime
import decimal
import re
import json


class PerformanceConfig:
    """Performance settings; centralizes performance-related parameters."""

    QUERY_TIMEOUT = 30  # Query timeout (seconds)
    DECIMAL_PLACES = 2  # Decimal places for formatting
    CACHE_MAX_SIZE = 5  # Database connection cache size
    ENABLE_PERFORMANCE_LOG = True  # Whether to enable performance logging


def write_json(path, data):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def read_json(path):
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    return data


def read_text(filename) -> str:
    data = []
    with open(filename, "r", encoding="utf-8") as file:
        for line in file.readlines():
            line = line.strip()
            data.append(line)
    return data


def save_raw_text(filename, content):
    with open(filename, "w", encoding="utf-8") as file:
        file.write(content)


def read_map_file(path):
    data = {}
    with open(path, "r", encoding="utf-8") as f:
        for line in f.readlines():
            line = line.strip().split("\t")
            data[line[0]] = line[1].split("、")
            data[line[0]].append(line[0])
    return data


def save_json(target_file, js, indent=4):
    with open(target_file, "w", encoding="utf-8") as f:
        json.dump(js, f, ensure_ascii=False, indent=indent)


def is_email(string):
    pattern = r"^[\w\.-]+@[\w\.-]+\.\w+$"
    match = re.match(pattern, string)
    if match:
        return True
    else:
        return False


def examples_to_str(examples: list) -> list[str]:
    """
    from examples to a list of str
    """
    values = examples
    for i in range(len(values)):
        if isinstance(values[i], datetime.date):
            values = [values[i]]
            break
        elif isinstance(values[i], datetime.datetime):
            values = [values[i]]
            break
        elif isinstance(values[i], decimal.Decimal):
            values[i] = str(float(values[i]))
        elif is_email(str(values[i])):
            values = []
            break
        elif "http://" in str(values[i]) or "https://" in str(values[i]):
            values = []
            break
        elif values[i] is not None and not isinstance(values[i], str):
            pass
        elif values[i] is not None and ".com" in values[i]:
            pass

    return [str(v) for v in values if v is not None and len(str(v)) > 0]

def _clean_and_validate_sql(sql_query: str) -> Optional[str]:
    """Clean and validate SQL using regex denylist patterns; blocks dangerous operations."""
    if not sql_query:
        return None

    try:
        # Strip markdown fences
        markdown_pattern = re.compile(
            r"```(?:sql)?\s*(.*?)\s*```", re.DOTALL | re.IGNORECASE
        )
        match = markdown_pattern.search(sql_query)
        cleaned_sql = match.group(1).strip() if match else sql_query.strip()
        if not cleaned_sql:
            return None

        # Collapse extra whitespace
        cleaned_sql = re.sub(r"\s+", " ", cleaned_sql).strip()
        sql_lower = cleaned_sql.lower()

        # Denylist: block dangerous SQL
        dangerous_patterns = [
            r'^\s*(drop|delete|truncate|update|insert|create|alter|grant|revoke)\s+',  # Dangerous DDL/DML
            r'\b(exec|execute|sp_|xp_)\b',  # Stored procedure execution
            r'\b(into\s+outfile|load_file|load\s+data)\b',  # File operations
            r'\b(union\s+all\s+select.*into|select.*into)\b',  # SELECT INTO
            r';\s*(drop|delete|truncate|update|insert|create|alter)',  # Chained dangerous statements
            r'\b(benchmark|sleep|waitfor|delay)\b',  # Timing attacks
            r'@@|information_schema\.(?!columns|tables|schemata)',  # System vars / sensitive metadata
        ]

        for pattern in dangerous_patterns:
            if re.search(pattern, sql_lower, re.IGNORECASE):
                raise ValueError("Dangerous SQL operation detected; query rejected")

        return cleaned_sql

    except ValueError:
        raise
    except Exception:
        return None


def safe_port_conversion(port_value, logger=None) -> Optional[int]:
    """Safely convert a port value to int.

    Args:
        port_value: Port as str, int, or None
        logger: Optional logger

    Returns:
        Integer port, or None if invalid
    """
    if port_value is None:
        return None
    try:
        return int(port_value)
    except (ValueError, TypeError):
        if logger:
            logger.warning(f"Invalid port number: {port_value}")
        return None


def format_numeric_values(results: List[Dict], decimal_places: int = 2, logger=None) -> List[Dict]:
    """Format numeric values to avoid scientific notation; fixed decimal places.

    Args:
        results: List of row dicts
        decimal_places: Decimal places (default 2)
        logger: Optional logger

    Returns:
        Formatted result rows
    """
    if not results:
        return results

    formatted_results = []
    for row in results:
        formatted_row = {}
        for key, value in row.items():
            formatted_row[key] = format_single_value(value, decimal_places)
        formatted_results.append(formatted_row)

    if logger:
        logger.debug(f"Numeric formatting done, processed {len(formatted_results)} rows")
    return formatted_results


def format_single_value(value, decimal_places: int = 2) -> Any:
    """Format a single value with performance-friendly logic.

    Args:
        value: Value to format
        decimal_places: Decimal places (default 2)

    Returns:
        Formatted value
    """
    if value is None or isinstance(value, bool):
        return value

    if not isinstance(value, (int, float)):
        return value

    try:
        if isinstance(value, int):
            return str(value)

        if isinstance(value, float):
            if not (value == value):  # NaN check, faster than pd.isna()
                return None

            if abs(value) == float("inf"):
                return str(value)

            if value.is_integer():
                return str(int(value))  # 1.0 -> "1" not "1.00"
            else:
                return f"{value:.{decimal_places}f}"

        return str(value)

    except (ValueError, OverflowError, TypeError, AttributeError):
        return str(value) if value is not None else None


def create_config_hash(db_config: Dict[str, Any]) -> str:
    """Build a cache key hash from DB config.

    Args:
        db_config: Dict with db_type, host, port, dbname, user, etc.

    Returns:
        16-char MD5 hex string
    """
    config_str = f"{db_config.get('db_type')}|{db_config.get('db_host')}|{db_config.get('db_port')}|{db_config.get('db_name')}|{db_config.get('db_user')}"
    return hashlib.md5(config_str.encode()).hexdigest()[:16]


class LRUCache:
    """LRU cache for database service instances (OrderedDict-based)."""

    def __init__(self, max_size: int = 5):
        """Initialize LRU cache.

        Args:
            max_size: Max entries (default 5)
        """
        self._cache = OrderedDict()
        self._max_size = max_size

    def get(self, key: str) -> Optional[Any]:
        """Get value and mark as most recently used.

        Args:
            key: Cache key

        Returns:
            Cached value or None
        """
        if key in self._cache:
            self._cache.move_to_end(key)
            return self._cache[key]
        return None

    def put(self, key: str, value: Any) -> None:
        """Insert or update an entry.

        Args:
            key: Cache key
            value: Value to store
        """
        if key in self._cache:
            self._cache.move_to_end(key)
        else:
            if len(self._cache) >= self._max_size:
                self._cache.popitem(last=False)
        self._cache[key] = value

    def clear(self) -> None:
        """Clear all entries."""
        self._cache.clear()

    def size(self) -> int:
        """Current number of entries."""
        return len(self._cache)

    def contains(self, key: str) -> bool:
        """Whether key exists."""
        return key in self._cache


class Logger:
    """Logging helper."""

    def __init__(self, config: LoggerConfig):
        self.config = config
        self._setup_logging()

    def _setup_logging(self):
        """Configure logging."""
        handlers = [logging.StreamHandler()]

        # Only add FileHandler if log_file is not None
        # if self.config.log_file is not None:
        #     handlers.append(logging.FileHandler(self.config.log_file, encoding="utf-8"))

        log_level = self.config.log_level.upper()

        logging.basicConfig(
            level=getattr(logging, log_level),
            format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
            handlers=handlers,
            force=True,
        )
        self.logger = logging.getLogger("dict_generator")

    def get_logger(self) -> logging.Logger:
        """Return the logger instance."""
        return self.logger
