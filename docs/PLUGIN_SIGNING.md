# Assinatura segura de plugins (Dify self-hosted)

Este fluxo permite **manter a verificação de assinatura ligada** no *plugin daemon* e mesmo assim instalar o **LM DB Schema RAG** (ou outro `.difypkg` teu), **sem** aceitar pacotes arbitrários da internet: só passam plugins assinados com **a tua chave privada**, e o servidor só confia na **tua chave pública**.

Documentação oficial (inglês): [Signing plugins for third-party signature verification](https://docs.dify.ai/plugins/publish-plugins/signing-plugins-for-third-party-signature-verification) (espelho: [legacy-docs](https://legacy-docs.dify.ai/plugins/publish-plugins/signing-plugins-for-third-party-signature-verification)).

> Disponível na **Community Edition** self-hosted; não é o mesmo modelo que o marketplace cloud da Dify.

---

## 1. Modelo de segurança (resumo)

| Artefacto | Onde fica | Quem vê |
|-----------|-----------|---------|
| **Chave privada** `.private.pem` | Máquina segura de *build* ou **GitHub Secret** (CI) encriptado | Só quem assina pacotes |
| **Chave pública** `.public.pem` | Servidor Dify, no volume montado no *plugin daemon* | Qualquer admin; não assina pacotes |

- Com a **chave privada** comprometida, um atacante pode assinar **qualquer** plugin que o teu Dify aceitaria. Trata-a como credencial (rotação se vazar, acesso mínimo, nunca em git).
- O Dify só instala `.difypkg` cuja assinatura confere com **uma das chaves públicas** que configuraste.

---

## 2. Gerar o par de chaves (uma vez)

Usa o binário **dify-plugin** dos [releases do daemon](https://github.com/langgenius/dify-plugin-daemon/releases). O subcomando **`signature`** **não existe** em versões muito antigas do CLI (ex.: **0.0.6**); usa **≥ 0.2** ou a mesma linha que o teu *plugin daemon* (o CI deste repo usa **0.5.4** para empacotar e assinar).

```bash
chmod +x ./dify-plugin-linux-amd64   # ou dify-plugin-darwin-arm64, etc.
./dify-plugin-linux-amd64 signature generate -f lm_db_schema_rag_signing
```

Gera, no diretório atual:

- `lm_db_schema_rag_signing.private.pem` — **segredo** (assinar)
- `lm_db_schema_rag_signing.public.pem` — **público** (verificar no servidor)

Guarda a privada fora do repositório (ex.: gestor de secrets, cofre).

---

## 3. Empacotar e assinar

```bash
# 1) Pacote normal (como no CI)
./dify-plugin-linux-amd64 plugin package . -o lm_db_schema_rag-1.0.0.difypkg

# 2) Assinar (produz ficheiro com sufixo .signed.difypkg)
./dify-plugin-linux-amd64 signature sign lm_db_schema_rag-1.0.0.difypkg -p lm_db_schema_rag_signing.private.pem
```

Resultado típico: `lm_db_schema_rag-1.0.0.signed.difypkg`

**Verificar localmente** antes de publicar:

```bash
./dify-plugin-linux-amd64 signature verify lm_db_schema_rag-1.0.0.signed.difypkg -p lm_db_schema_rag_signing.public.pem
```

*(Sem `-p`, o CLI pode validar contra a chave do marketplace oficial — o teu pacote **não** passará.)*

---

## 4. GitHub Actions (automático neste repo)

O workflow **`.github/workflows/release-attach-difypkg.yml`**, ao publicar uma **Release**, gera o `.difypkg` e **assina** se existir o secret:

| Secret | Conteúdo |
|--------|----------|
| **`PLUGIN_SIGNING_PRIVATE_PEM`** | Texto completo do **`.private.pem`** (linhas `BEGIN` / `END`). Secret **multilinha**. Sem isto, o `.difypkg` na release fica **sem assinatura** e o Dify com verificação ligada **rejeita**. |
| **`PLUGIN_SIGNING_PUBLIC_PEM`** | Opcional. Conteúdo do **`.public.pem`** do **mesmo** par. Se estiver definido **e** a privada também, o CI corre **`signature verify`** antes do upload (apanha PEM trocado ou corrupto). |

- Com a **privada** definida, o ficheiro na release mantém o nome `{name}-{version}.difypkg`, mas o conteúdo fica **assinado**.
- **Regerar o asset** sem nova versão: **Actions** → **Attach difypkg to release** → **Run workflow** → `tag` = ex. `v1.0.0`.

**O que tens de fazer uma vez:** gerar o par (secção 2), secret da **privada** no GitHub, ficheiro da **pública** no volume do Dify + env `THIRD_PARTY_*` (secção 7).

---

## 5. Script local (`scripts/package-and-sign.sh`)

Mesmo fluxo que o CI, na tua máquina:

```bash
export DIFY_PLUGIN_CLI=/caminho/para/dify-plugin-darwin-arm64   # ou linux-amd64
./scripts/package-and-sign.sh /caminho/seguro/lm_db_schema_rag_signing.private.pem
```

Gera `{name}-{version}.difypkg` na raiz do plugin, **assinado** (sobrescreve o nome final sem `.signed.` no meio).

---

## 6. Publicar o ficheiro **assinado**

- **Release GitHub:** o workflow anexa o `.difypkg` assinado quando o secret está configurado.
- **Manual:** usa o script da secção 5 e anexa o `.difypkg` à release.

---

## 7. Configurar o Dify (plugin daemon)

### 7.1 Colocar a chave **pública** onde o contentor vê

No projeto Docker do Dify, o volume típico é `docker/volumes/plugin_daemon` montado em **`/app/storage`** no serviço `plugin_daemon`.

```bash
mkdir -p docker/volumes/plugin_daemon/public_keys
cp lm_db_schema_rag_signing.public.pem docker/volumes/plugin_daemon/public_keys/
```

### 7.2 Variáveis de ambiente (exemplo)

No `plugin_daemon` (por exemplo via `docker-compose.override.yaml`):

```yaml
services:
  plugin_daemon:
    environment:
      FORCE_VERIFYING_SIGNATURE: "true"
      THIRD_PARTY_SIGNATURE_VERIFICATION_ENABLED: "true"
      THIRD_PARTY_SIGNATURE_VERIFICATION_PUBLIC_KEYS: /app/storage/public_keys/lm_db_schema_rag_signing.public.pem
```

- Várias chaves: lista separada por **vírgulas** em `THIRD_PARTY_SIGNATURE_VERIFICATION_PUBLIC_KEYS`.
- O caminho é **dentro do contentor** (`/app/storage/...`), não só no host.

Reinicia:

```bash
cd docker
docker compose down && docker compose up -d
```

---

## Diagnóstico: ainda aparece **bad signature** no Dify

O instalador valida o `.difypkg` no **plugin daemon**. Este erro quase sempre é **configuração**, não o “nome” do ficheiro na UI.

### 1) O ficheiro na GitHub Release está mesmo **assinado**?

No GitHub: **Actions** → workflow **“Attach difypkg to release”** → abre a última execução para a tag **`v1.0.0`** (ou a que estiveres a usar).

- Se vires **`::warning:: PLUGIN_SIGNING_PRIVATE_PEM not set`** → o artefacto foi enviado **sem assinatura**. Com `FORCE_VERIFYING_SIGNATURE=true`, **vai falhar sempre**.
  - Cria o secret **`PLUGIN_SIGNING_PRIVATE_PEM`** (PEM completo da chave privada) e volta a gerar o asset: **Actions** → **Attach difypkg to release** → **Run workflow** → `tag` = `v1.0.0` (este repo suporta reexecução manual).

- Se vires **`Package was signed in CI`** → o CI assinou; o problema costuma ser o servidor Dify (passos abaixo).

Opcional: adiciona também o secret **`PLUGIN_SIGNING_PUBLIC_PEM`** (conteúdo do `.public.pem` **que corresponde** à privada do secret). O CI corre então **`signature verify`** antes do upload — se isto falhar, o PEM no GitHub não bate certo com a privada.

### 2) No Dify: chave **pública** e variáveis certas?

Só **assinar** no CI não chega: o daemon tem de **confiar na tua chave pública**.

Tens de ter **ao mesmo tempo** (valores exemplificativos):

| Variável | Valor típico |
|----------|----------------|
| `FORCE_VERIFYING_SIGNATURE` | `true` |
| `THIRD_PARTY_SIGNATURE_VERIFICATION_ENABLED` | `true` |
| `THIRD_PARTY_SIGNATURE_VERIFICATION_PUBLIC_KEYS` | Caminho **dentro do contentor** para o `.public.pem` (ex.: `/app/storage/public_keys/o_teu_ficheiro.public.pem`) |

Erros frequentes:

- **`THIRD_PARTY_SIGNATURE_VERIFICATION_ENABLED=false` ou omitida** — o daemon pode só aceitar assinaturas “oficiais” do marketplace, e o teu pacote **nunca** passa.
- **Ficheiro `.public.pem` no host mas caminho errado no contentor** — o caminho na env tem de ser onde o ficheiro aparece **dentro** do `plugin_daemon` (muitas vezes sob `/app/storage/...`).
- **Chave pública no servidor ≠ par da chave privada usada no GitHub** — gera de novo o par, atualiza secret + ficheiro no volume + reinicia o daemon.

### 3) Versão do plugin daemon

Alinha a imagem / binário do **plugin daemon** do Dify com uma linha recente (a mesma família que o CLI **0.5.x** usado no CI). Muito antigo pode comportar-se mal com o formato de assinatura atual.

### 4) Caminho rápido só para testar

Só em ambiente em que aceites o risco: `FORCE_VERIFYING_SIGNATURE=false` no `.env` do Docker (ver [GITHUB_INSTALL_PLUGIN.md](GITHUB_INSTALL_PLUGIN.md#erro-bad-signature-plugin-verification)).

---

## 8. Boas práticas

1. **Rotação:** novo par de chaves → atualizar `.public.pem` no servidor, atualizar o secret `PLUGIN_SIGNING_PRIVATE_PEM` no GitHub, e re-assinar releases; podes manter duas públicas em `THIRD_PARTY_SIGNATURE_VERIFICATION_PUBLIC_KEYS` durante a transição.
2. **Não** commits de `.private.pem`; o `.gitignore` do repo ignora `*.private.pem`.
3. Alinha a versão do **dify-plugin** CLI (releases do daemon) com a do *plugin daemon* no Dify.

---

## 9. Relação com `FORCE_VERIFYING_SIGNATURE=false`

- **`false`:** desliga exigência de assinatura (rápido, menos seguro para ambientes expostos).
- **Fluxo deste documento:** mantém verificação **ligada** e restringe a **pacotes assinados pelas tuas chaves** — é o caminho “seguro” para plugins próprios fora do marketplace oficial.
