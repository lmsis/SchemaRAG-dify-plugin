# Tradução (EN / pt-BR) — Pontos de atenção

Este documento resume o que foi alterado na internacionalização do plugin SchemaRAG para Dify e onde ainda existe texto não inglês **de propósito**.

## O que foi padronizado

- **Código Python** (comentários, docstrings, mensagens de log, `raise`/`ValueError` e textos devolvidos ao utilizador nas tools): **inglês**, exceto onde indicado abaixo.
- **Ficheiros de configuração** (`config.py`, `utils.py`, `requirements.txt`, `pyproject.toml`): comentários em **inglês**.
- **Documentação Markdown** (`README.md`, `README_CN.md`, `USAGE.md`, `UPDATE.md`, `CLAUDE.md`, `docs/*`, `core/llm_plot/README.md`): conteúdo que estava em chinês passou para **inglês** (o nome `README_CN.md` mantém-se por compatibilidade de links; o conteúdo foi alinhado em inglês com nota no topo, conforme aplicável).
- **YAML das tools e do provider**: mantidos **`en_US`**, **`zh_Hans`** (chinês simplificado para UI Dify em chinês) e **`pt_BR`** (português do Brasil) onde a plataforma suporta múltiplas línguas.
- **`manifest.yaml`**: `en_US`, `ja_JP`, `zh_Hans`, `pt_BR` — `ja_JP` não foi traduzido a partir do pedido (já estava em japonês).

## Onde o chinês (ou CJK) permanece de forma intencional

1. **`zh_Hans` em `*.yaml` do provider, tools, `manifest.yaml` e `demo/text2sql-workflow.yml`**  
   São strings de interface para utilizadores que usam o Dify em chinês. Não foram removidas.

2. **`service/cache/utils.py`**  
   Lista de **stopwords / frases em chinês** usada na **normalização de consultas** para cache. Traduzir ou apagar quebraria o comportamento para perguntas em chinês.

3. **`prompt/components/context_formatter.py`**  
   **Palavras de referência em chinês** (e outras) para detetar follow-ups em conversas multilingues. São dados linguísticos, não apenas documentação.

4. **`test/test_chinese_fonts.py`**  
   Títulos e rótulos em **chinês** nos dados de teste servem para validar **renderização de fontes CJK** nos gráficos. O ficheiro está documentado em inglês; os literais em chinês são **fixtures** necessários ao teste.

5. **`CLAUDE.md`**  
   Exemplos de YAML de tools podem ainda mostrar `zh_Hans:` como **ilustração** do padrão i18n do Dify.

## Dúvidas que poderiam ter sido perguntas ao utilizador

- **Prompts LLM** (`prompt/*.py`): o corpo dos prompts para o modelo já era maioritariamente em inglês; comentários e docstrings foram passados para inglês. Títulos entre `【】` foram alinhados a títulos em inglês onde fazia sentido, sem alterar a semântica das instruções ao modelo.
- **Mensagens de erro expostas ao utilizador final no chat**: foram unificadas em **inglês** nas tools (comportamento padrão quando não há i18n por mensagem). O utilizador pode mais tarde introduzir chaves de tradução se quiser respostas multilingues nas yields das tools.

## Verificação e CI local

- **`uv run pytest` / `uv sync`** neste repositório pode falhar em **macOS ARM** por causa do pacote **`dmpython`** (Dameng), que não disponibiliza wheel para essa plataforma. Isto é uma limitação de ambiente, não da tradução.
- Foi executado **`python3 -m compileall`** sobre o projeto para validar sintaxe Python.

## Mensagens no chat (EN / pt-BR / zh)

- Ficheiro central: **`tools/tool_messages.py`** — chaves `TOOL_UI_STRINGS` com `en_US`, `pt_BR`, `zh_Hans`.
- Parâmetro opcional **`ui_language`** nas tools **Text to Data**, **SQL Executor** e **SQL Executor (custom)** (`text2data.yaml`, `sql_executer.yaml`, `sql_executer_cust.yaml`): valor `en_US` (padrão), `pt_BR` ou `zh_Hans`. Controla textos de estado devolvidos ao chat (passos de SQL, sucesso/falha, refinador, resultado vazio, etc.).
- Funções auxiliares: `t()`, `think_block_start()`, `think_block_end()`, `normalize_ui_language()`.

## Revisão de `pt_BR` nos YAML

- Foram corrigidos rótulos em inglês incorretos ou genéricos: por exemplo **SQL Executer → SQL Executor**, **Max Line → Max rows**, **Top K** em PT como **Número de resultados (top K)**, tool custom **Custom SQL executor**.
- Onde `pt_BR` coincide com nomes próprios (**MySQL**, **JSON**, **Markdown**), mantém-se igual ao inglês por convenção.

## Manutenção futura

- Ao adicionar novas tools ou credenciais no `provider.yaml`, repetir o trio **`en_US` / `zh_Hans` / `pt_BR`** para labels e descrições humanas.
- Novas mensagens visíveis no chat: adicionar chave em **`tools/tool_messages.py`** e usar `t(ui_lang, ...)` com **`ui_language`** exposto no YAML se aplicável.
- Novos comentários no código: preferir **inglês** para consistência com o restante código traduzido.
