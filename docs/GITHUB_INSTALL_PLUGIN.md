# Instalar o plugin a partir do GitHub (Dify)

No diálogo **Install plugin from GitHub**, o Dify só mostra ficheiros **`.difypkg`** que estão anexados como **assets** da release. O ZIP/tarball de código que o GitHub gera automaticamente **não** serve para esse ecrã.

## Por que o dropdown “Select package” fica vazio

- Criaste uma release com tag (ex.: `v0.2.3`) mas **sem** subir um `.difypkg`.
- O pacote na release vem do workflow **`release-attach-difypkg.yml`** (ou upload manual); os workflows que enviavam PR para `dify-plugins` estão **desativados** neste repo.

## Solução automática (recomendado)

Foi adicionado o workflow **`.github/workflows/release-attach-difypkg.yml`**, que em cada **release published**:

1. Faz checkout da tag.
2. Gera `{name}-{version}.difypkg` (ex.: `lm_db_schema_rag-0.2.3.difypkg`) com o CLI oficial.
3. Faz **upload** desse ficheiro para a mesma release.

**Passos:**

1. Faz **commit** e **push** deste workflow para `main`.
2. Na release **já existente** `v0.2.3`, podes:
   - **Actions** → workflow **“Attach difypkg to release”** → **Run workflow** não existe para `release` events; ou
   - **Editar a release**, mudar para draft e voltar a publicar, ou criar uma release nova (ex. `v0.1.8`) para disparar o workflow; ou
3. **Mais simples para a release atual:** usar a solução manual abaixo **uma vez**.

## Solução manual (release já criada)

1. Instala o CLI **dify-plugin** para o teu sistema a partir de  
   [langgenius/dify-plugin-daemon releases](https://github.com/langgenius/dify-plugin-daemon/releases)  
   (ex.: `dify-plugin-darwin-arm64` no Mac Apple Silicon).

2. Na raiz do repositório do plugin:

   ```bash
   chmod +x /caminho/para/dify-plugin-darwin-arm64
   /caminho/para/dify-plugin-darwin-arm64 plugin package . -o lm_db_schema_rag-0.2.3.difypkg
   ```

   Ajusta o nome do ficheiro de saída a `lm_db_schema_rag-<versão do manifest>.difypkg`.

3. No GitHub: **Releases** → abre a release **v0.2.3** → **Edit release** → arrasta o `.difypkg` para **Attach binaries** → guarda.

4. No Dify, volta a **Install from GitHub** e escolhe a versão; o pacote deve aparecer no dropdown.

## Nome do pacote no Dify

O instalador lista todos os `.difypkg` da release. O nome típico é **`lm_db_schema_rag-0.2.3.difypkg`** (campo `name` + `version` do `manifest.yaml`). Se no teu ecrã aparecer outro padrão, é só o rótulo da UI; o importante é a extensão **`.difypkg`**.
