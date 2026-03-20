# Release notes

## Sugestões de versão e ficheiros a alterar

| Item | Valor |
|------|--------|
| **Versão atual no repo** | `0.2.2` — plugin id **`lmsis/lm_db_schema_rag`** |
| **Próxima versão sugerida** | `0.2.3` ou `0.3.0` — conforme alterações |

**Ao publicar, atualizar a versão em todos estes sítios:**

1. **`manifest.yaml`** — campo `version:` (linha ~1) **e** `meta.version:` (linha ~38).
2. **`pyproject.toml`** — `[project].version`.
3. **`README.md`** — badge `version-0.1.x` na URL do shields.io **e** linha **Version:** no texto.
4. **`UPDATE.md`** — histórico de versões (inclui `0.2.2`, `0.2.1`, `0.2.0` e notas de breaking).

**Opcional (conforme o vosso fluxo):**

- Mencionar no corpo do GitHub Release os ficheiros novos: `tools/tool_messages.py`, `docs/TRADUCAO_ATENCAO.md`, `RELEASE_NOTES.md`.
- Se usarem **GitHub Release → plugin publish** (`.github/workflows/plugin-publish.yml`), o pacote `.difypkg` deve ser gerado **depois** do bump de versão.

**Compatibilidade / migração para utilizadores Dify**

- **`ui_language`** é opcional; o padrão é **`en_US`**. Fluxos e agentes existentes comportam-se como antes até alguém escolher **pt_BR** ou **zh_Hans** nos nós das tools afetadas.
- Não é necessário alterar workflows guardados só por causa deste release; só se quiserem mensagens de estado no chat noutro idioma.

---

Use o bloco **English** abaixo na descrição do release no GitHub se quiser alcance internacional; o bloco **Português** resume o mesmo para a equipa.

---

## English (copy for GitHub Release)

### Summary

Major **internationalization (i18n)** pass: English as default in code and logs, **Brazilian Portuguese (`pt_BR`)** and **Simplified Chinese (`zh_Hans`)** where Dify supports multi-language labels. Centralized **chat-facing tool strings** with an optional **`ui_language`** parameter.

### Added

- **`tools/tool_messages.py`** — localized UI strings (`en_US`, `pt_BR`, `zh_Hans`) and helpers: `t()`, `normalize_ui_language()`, `think_block_start()`, `think_block_end()`.
- **Optional tool parameter `ui_language`** (default `en_US`) in:
  - Text to Data (`text2data.yaml` / `text2data.py`)
  - SQL Executor (`sql_executer.yaml` / `sql_executer.py`)
  - Custom SQL Executor (`sql_executer_cust.yaml` / `sql_executer_cust.py`)
- **`docs/TRADUCAO_ATENCAO.md`** — maintenance notes (also describes intentional remaining Chinese in YAML `zh_Hans`, cache stopwords, CJK font tests).
- **`RELEASE_NOTES.md`** — this file, for GitHub Releases and internal tracking.

### Changed

- **Python**: comments, docstrings, logger messages, and user-visible errors in tools/services/core/prompt aligned to **English** (except intentional linguistic data and i18n YAML).
- **Tool YAML / `provider.yaml` / `manifest`**: `en_US` + `zh_Hans` + **`pt_BR`** reviewed; several **pt_BR** strings improved; labels fixed (e.g. **SQL Executor**, **Max rows**, **Custom SQL executor**).
- **`text2data`**: status messages (SQL generation banner, execution success/failure, refiner, empty result, summary user prompt) follow **`ui_language`**.
- **SQL executors**: config / URL / empty-result messages follow **`ui_language`**.
- **Docs** (`README`, `docs/*`, `USAGE`, `UPDATE`, `CLAUDE`, etc.): Chinese content translated to **English** where applicable.
- **`utils.py` / `config.py`**: comments and messages in English; SQL validation error message in English.
- **`requirements.txt` / `pyproject.toml`**: comments in English.

### Notes

- **`zh_Hans`** entries in YAML are **kept** for Chinese UI.
- **`service/cache/utils.py`** and **`prompt/components/context_formatter.py`** still contain **Chinese tokens** by design (query normalization / follow-up heuristics).
- **`test/test_chinese_fonts.py`** keeps **Chinese literals** as CJK font fixtures.
- **`uv sync` / tests** may fail on **macOS ARM** if **`dmpython`** has no wheel (Dameng); unrelated to i18n.

### Breaking changes

None. New parameters are optional with safe defaults.

---

## Português (resumo)

### Resumo

Grande passagem de **internacionalização**: inglês como padrão em código e logs; **português (Brasil)** e **chinês simplificado** nos campos suportados pelo Dify (`en_US` / `pt_BR` / `zh_Hans`). Mensagens visíveis no chat das tools centralizadas em **`tools/tool_messages.py`**, com parâmetro opcional **`ui_language`**.

### Novo

- Módulo **`tools/tool_messages.py`** com strings e funções de locale.
- Parâmetro **`ui_language`** nas tools **Text to Data**, **SQL Executor** e **Executor SQL personalizado**.
- **`docs/TRADUCAO_ATENCAO.md`** e **`RELEASE_NOTES.md`**.

### Alterado

- Código Python (tools, service, core, prompt, provider, testes): comentários e mensagens em **inglês**; YAMLs e documentação alinhados; **pt_BR** revisto nos YAML.
- **Text to Data** e **executores SQL**: textos de estado no chat conforme **`ui_language`**.
- Correções de rótulos em inglês (**SQL Executor**, **Max rows**, etc.).

### Observações

- Chinês em **`zh_Hans`** nos YAML mantido para UI em chinês.
- Listas linguísticas em cache/context formatter e dados de teste de fontes CJK **mantidos de propósito**.
- Possível falha de **`uv`** em **macOS ARM** por causa do pacote **Dameng** (`dmpython`).

### Breaking changes

Nenhum. Parâmetros novos são opcionais.

---

## Sugestões para o GitHub

### Título do Release (exemplo)

`v0.2.2 — LM DB Schema RAG: fix YAML in tool specs for dify-plugin package`

### Tag Git (exemplo)

`v0.2.2` ou `0.2.2` — *usar a mesma convenção dos releases anteriores do repositório.*

### Mensagem de commit (escolher uma)

```
feat(i18n): default EN, pt_BR/zh_Hans YAML, tool_messages and ui_language
```

```
chore(i18n): localize UI, add tool_messages.py and optional ui_language
```

---

## Checklist antes de publicar

- [ ] Bumped **`manifest.yaml`**: `version` **e** `meta.version`.
- [ ] Bumped **`pyproject.toml`** `version`.
- [ ] Bumped **`README.md`** (badge + texto **Version:**).
- [ ] Atualizado **`UPDATE.md`** (se aplicável).
- [ ] Ajustado o número da versão no **título** do GitHub Release se não for `v0.2.2`.
- [ ] `python3 -m compileall` ou `uv run` / testes num ambiente compatível (ex.: Linux se Dameng for obrigatório no lockfile).
- [ ] Criada **tag** e **GitHub Release** com o bloco **English** (ou PT) no corpo.
- [ ] Gerado / publicado **`.difypkg`** após o bump, se fizer parte do vosso pipeline.
