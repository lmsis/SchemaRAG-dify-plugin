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
| **`PLUGIN_SIGNING_PRIVATE_PEM`** | Texto completo do ficheiro **`.private.pem`** (incluindo linhas `BEGIN` / `END`). Usa “New repository secret” e cola o PEM em **multilinha**. |

- Com o secret definido, o artefacto enviado para a release continua a chamar-se `{name}-{version}.difypkg`, mas o conteúdo é **já assinado** (o CI substitui o pacote não assinado após `signature sign`).
- **Sem** o secret, o workflow emite um aviso e faz upload do pacote **sem assinatura** (comportamento anterior).

**O que tens de fazer uma vez:** gerar o par de chaves (secção 2), colocar a **privada** no secret acima, e a **pública** no servidor Dify (secção 6).

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

## 8. Boas práticas

1. **Rotação:** novo par de chaves → atualizar `.public.pem` no servidor, atualizar o secret `PLUGIN_SIGNING_PRIVATE_PEM` no GitHub, e re-assinar releases; podes manter duas públicas em `THIRD_PARTY_SIGNATURE_VERIFICATION_PUBLIC_KEYS` durante a transição.
2. **Não** commits de `.private.pem`; o `.gitignore` do repo ignora `*.private.pem`.
3. Alinha a versão do **dify-plugin** CLI (releases do daemon) com a do *plugin daemon* no Dify.

---

## 9. Relação com `FORCE_VERIFYING_SIGNATURE=false`

- **`false`:** desliga exigência de assinatura (rápido, menos seguro para ambientes expostos).
- **Fluxo deste documento:** mantém verificação **ligada** e restringe a **pacotes assinados pelas tuas chaves** — é o caminho “seguro” para plugins próprios fora do marketplace oficial.
