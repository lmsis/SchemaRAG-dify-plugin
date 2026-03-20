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

---

## Erro: bad signature (plugin verification)

Mensagem típica: `PluginDaemonBadRequestError: plugin verification has been enabled, and the plugin you want to install has a bad signature`.

**Porquê:** Em instalações **self-hosted**, o *plugin daemon* do Dify pode exigir que o `.difypkg` tenha uma **assinatura** reconhecida. Pacotes gerados com `dify-plugin package` (CI ou local) **não** trazem a mesma assinatura dos plugins do marketplace oficial — por isso a instalação falha com verificação ativada.

### Opção A — Desativar a verificação forçada (ambiente interno / confiança no pacote)

1. No servidor onde corre o Dify (pasta **`docker/`** do projeto [langgenius/dify](https://github.com/langgenius/dify)), edita o **`.env`** (ou o ficheiro que o teu `docker compose` usa).
2. Garante:

   ```env
   FORCE_VERIFYING_SIGNATURE=false
   ```

3. **Reinicia** os contentores para o *plugin daemon* apanhar a variável, por exemplo:

   ```bash
   cd docker
   docker compose down
   docker compose up -d
   ```

4. Se o erro continuar, confirma na tua versão do Dify se **`FORCE_VERIFYING_SIGNATURE`** está **repassada ao serviço `plugin_daemon`** no `docker-compose.yaml` (em algumas versões a variável tinha de existir no `environment` desse serviço — ver [issue #14184](https://github.com/langgenius/dify/issues/14184)).

> **Segurança:** com `false`, o daemon aceita pacotes não assinados como o deste repositório. Usa só em ambientes onde confias no `.difypkg` (ex.: a tua própria release no GitHub).

### Opção B — Manter verificação e assinar o pacote

Se precisas de verificação ativa, segue a documentação oficial para **par de chaves e assinatura** do plugin, por exemplo: [Third-party signature verification](https://docs.dify.ai/plugin-dev-en/0312-third-party-signature-verification) (comando `dify signature` no CLI, conforme a versão do *dify-plugin-daemon*).
