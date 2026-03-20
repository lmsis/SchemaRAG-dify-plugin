"""
Tool parameter validation and extraction helpers.
"""
from typing import Any, Tuple, Union, Optional


def validate_and_extract_text2sql_parameters(
    tool_parameters: dict[str, Any],
    max_content_length: int = 10000,
    default_top_k: int = 5,
    default_dialect: str = "mysql",
    default_retrieval_model: str = "semantic_search",
    default_memory_window: int = 3
) -> Union[Tuple[str, Any, str, str, int, str, str, str, bool, int, bool, bool], str]:
    """
    Validate and extract Text2SQL tool parameters.

    Args:
        tool_parameters: Raw tool parameter dict
        max_content_length: Max question length
        default_top_k: Default top_k
        default_dialect: Default SQL dialect
        default_retrieval_model: Default retrieval mode
        default_memory_window: Default memory window size

    Returns:
        On success: (dataset_id, llm_model, content, dialect, top_k,
                    retrieval_model, custom_prompt, example_dataset_id,
                    memory_enabled, memory_window_size, reset_memory, cache_enabled)
        On failure: error message string
    """
    dataset_id = tool_parameters.get("dataset_id")
    if not dataset_id or not dataset_id.strip():
        return "dataset_id is required"

    llm_model = tool_parameters.get("llm")
    if not llm_model:
        return "LLM model configuration is required"

    content = tool_parameters.get("content")
    if not content or not content.strip():
        return "Question content is required"

    if len(content) > max_content_length:
        return (
            f"Question too long: max {max_content_length} characters, got {len(content)}"
        )

    dialect = tool_parameters.get("dialect", default_dialect)
    if dialect not in ["mysql", "postgresql", "sqlite", "oracle", "sqlserver", "mssql", "dameng", "doris"]:
        return f"Unsupported SQL dialect: {dialect}"

    top_k = tool_parameters.get("top_k", default_top_k)
    try:
        top_k = int(top_k)
        if top_k <= 0 or top_k > 50:
            return "top_k must be between 1 and 50"
    except (ValueError, TypeError):
        return "top_k must be a valid integer"

    retrieval_model = tool_parameters.get(
        "retrieval_model", default_retrieval_model
    )
    if retrieval_model not in [
        "semantic_search",
        "keyword_search",
        "hybrid_search",
        "full_text_search",
    ]:
        return f"Unsupported retrieval model: {retrieval_model}"

    custom_prompt = tool_parameters.get("custom_prompt", "")
    if custom_prompt and not isinstance(custom_prompt, str):
        return "custom_prompt must be a string"

    example_dataset_id = tool_parameters.get("example_dataset_id", "")
    if example_dataset_id and not isinstance(example_dataset_id, str):
        return "example_dataset_id must be a string"

    memory_enabled = tool_parameters.get("memory_enabled", "False")
    if isinstance(memory_enabled, str):
        memory_enabled = memory_enabled.lower() in ['true', '1', 'yes']
    elif not isinstance(memory_enabled, bool):
        memory_enabled = False

    memory_window_size = tool_parameters.get("memory_window_size", default_memory_window)
    try:
        memory_window_size = int(memory_window_size)
        if memory_window_size < 1 or memory_window_size > 10:
            return "memory_window_size must be between 1 and 10"
    except (ValueError, TypeError):
        return "memory_window_size must be a valid integer"

    reset_memory = tool_parameters.get("reset_memory", "False")
    if isinstance(reset_memory, str):
        reset_memory = reset_memory.lower() in ['true', '1', 'yes']
    elif not isinstance(reset_memory, bool):
        reset_memory = False

    cache_enabled = tool_parameters.get("cache_enabled", "true")
    if isinstance(cache_enabled, str):
        cache_enabled = cache_enabled.lower() in ['true', '1', 'yes']
    elif not isinstance(cache_enabled, bool):
        cache_enabled = True

    return (
        dataset_id.strip(),
        llm_model,
        content.strip(),
        dialect,
        top_k,
        retrieval_model,
        custom_prompt.strip() if custom_prompt else "",
        example_dataset_id.strip() if example_dataset_id else "",
        memory_enabled,
        memory_window_size,
        reset_memory,
        cache_enabled,
    )


def validate_and_extract_sql_executer_parameters(
    tool_parameters: dict[str, Any],
    default_max_rows: int = 500,
    logger=None
) -> Tuple[Optional[str], Optional[str], Optional[int], Optional[str]]:
    """
    Validate and extract SQL executor tool parameters.

    Args:
        tool_parameters: Raw tool parameter dict
        default_max_rows: Default row cap
        logger: Optional logger

    Returns:
        Tuple (sql_query, output_format, max_rows, error_msg).
        On success error_msg is None; on failure the first three are None.
    """
    sql_query = tool_parameters.get("sql")
    if not sql_query or not sql_query.strip():
        return None, None, None, "SQL query cannot be empty"

    output_format = tool_parameters.get("output_format", "json")
    if output_format not in ["json", "md"]:
        return None, None, None, "output_format must be 'json' or 'md'"

    max_line = tool_parameters.get("max_line", default_max_rows)
    try:
        max_rows = int(max_line)
        if max_rows <= 0:
            max_rows = default_max_rows
            if logger:
                logger.warning(
                    f"max_line must be > 0, using default {default_max_rows}: {max_line}"
                )
    except (ValueError, TypeError):
        max_rows = default_max_rows
        if logger:
            logger.warning(
                f"Invalid max_line, using default {default_max_rows}: {max_line}"
            )

    return sql_query.strip(), output_format, max_rows, None
