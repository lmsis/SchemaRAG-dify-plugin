"""
Localized strings for tool responses shown in the Dify chat (en_US / pt_BR / zh_Hans).

Use optional tool parameter ``ui_language`` (default en_US) to select the locale.
"""

from __future__ import annotations

from typing import Any

THINK_OPEN = "<think>"
THINK_CLOSE = "</think>"

_DEFAULT_LOCALE = "en_US"
_SUPPORTED = frozenset({"en_US", "pt_BR", "zh_Hans"})


def normalize_ui_language(raw: Any) -> str:
    """Map tool parameter value to a supported locale; default English."""
    if raw is None or raw == "":
        return _DEFAULT_LOCALE
    s = str(raw).strip().replace("-", "_")
    if s in _SUPPORTED:
        return s
    if s.lower() == "pt" or s.lower() == "pt_br":
        return "pt_BR"
    if s.lower() in ("zh", "zh_cn", "zh_hans", "zh_hans_cn"):
        return "zh_Hans"
    if s.lower() in ("en", "en_us"):
        return "en_US"
    return _DEFAULT_LOCALE


def t(locale: str, key: str, **kwargs: Any) -> str:
    """Format a UI string for ``locale``; unknown keys or locales fall back to en_US."""
    loc = normalize_ui_language(locale)
    row = TOOL_UI_STRINGS.get(key)
    if not row:
        return key
    template = row.get(loc) or row[_DEFAULT_LOCALE]
    if kwargs:
        return template.format(**kwargs)
    return template


def think_block_start(locale: str, key: str = "generating_sql_line") -> str:
    """Opening ``<think>`` block with localized banner line."""
    line = t(locale, key)
    return f"{THINK_OPEN}\n{line}\n\n"


def think_block_end(newlines: int = 1) -> str:
    """Closing ``</think>`` with trailing newlines (default one)."""
    n = max(1, newlines)
    return f"{THINK_CLOSE}{chr(10) * n}"


# Keys: en_US, pt_BR, zh_Hans — keep in sync when adding tool copy.
TOOL_UI_STRINGS: dict[str, dict[str, str]] = {
    "generating_sql_line": {
        "en_US": "💭 Generating SQL query",
        "pt_BR": "💭 Gerando consulta SQL",
        "zh_Hans": "💭 正在生成 SQL 查询",
    },
    "execution_succeeded_rows": {
        "en_US": "✅ Execution succeeded\n\nReturned {n} row(s)\n\n",
        "pt_BR": "✅ Execução concluída\n\nRetornada(s) {n} linha(s)\n\n",
        "zh_Hans": "✅ 执行成功\n\n共返回 {n} 行数据\n\n",
    },
    # Error body is appended in code (may contain braces)
    "execution_failed_prefix": {
        "en_US": "❌ Execution failed\n\n",
        "pt_BR": "❌ Falha na execução\n\n",
        "zh_Hans": "❌ 执行失败\n\n",
    },
    "execution_failed_suffix": {
        "en_US": "\n\n",
        "pt_BR": "\n\n",
        "zh_Hans": "\n\n",
    },
    "auto_fix_progress": {
        "en_US": "\n🔧 Auto-fix in progress...\n",
        "pt_BR": "\n🔧 Correção automática em andamento...\n",
        "zh_Hans": "\n🔧 自动修复中...\n",
    },
    # SQL is appended in code to avoid brace conflicts with str.format()
    "refine_success_prefix": {
        "en_US": "✨ Refined successfully ({n} attempt(s))\n\n",
        "pt_BR": "✨ Refinamento concluído ({n} tentativa(s))\n\n",
        "zh_Hans": "✨ 修复成功（尝试 {n} 次）\n\n",
    },
    "refine_success_suffix": {
        "en_US": "\n\n",
        "pt_BR": "\n\n",
        "zh_Hans": "\n\n",
    },
    "query_result_empty": {
        "en_US": "📊 **Query result**\n\nQuery ran successfully but returned no rows",
        "pt_BR": "📊 **Resultado da consulta**\n\nA consulta foi executada com sucesso, mas não retornou linhas",
        "zh_Hans": "📊 **查询结果**\n\n查询执行成功，但没有返回数据",
    },
    "summary_user_prompt": {
        "en_US": "Please produce a concise summary of the data above.",
        "pt_BR": "Produza um resumo conciso dos dados acima.",
        "zh_Hans": "请根据上述数据生成摘要。",
    },
    # SQL executer (provider DB)
    "sql_executer_db_config_error": {
        "en_US": "Error: database configuration is incomplete or invalid; check provider settings",
        "pt_BR": "Erro: configuração do banco incompleta ou inválida; verifique o provedor",
        "zh_Hans": "错误：数据库配置不完整或无效，请检查 provider 配置",
    },
    "sql_executer_no_rows": {
        "en_US": "Query ran successfully but returned no rows",
        "pt_BR": "Consulta executada com sucesso, mas sem linhas retornadas",
        "zh_Hans": "查询执行成功，但没有返回数据",
    },
    # Custom SQL executer (database_url)
    "sql_cust_url_required": {
        "en_US": "Error: database_url is required",
        "pt_BR": "Erro: database_url é obrigatória",
        "zh_Hans": "错误：必须提供 database_url",
    },
    "sql_cust_url_invalid": {
        "en_US": "Error: database_url is invalid or incomplete",
        "pt_BR": "Erro: database_url inválida ou incompleta",
        "zh_Hans": "错误：database_url 格式无效或不完整",
    },
    "sql_cust_url_parse_prefix": {
        "en_US": "Error: failed to parse database_url: ",
        "pt_BR": "Erro: falha ao analisar database_url: ",
        "zh_Hans": "错误：解析 database_url 失败: ",
    },
}
