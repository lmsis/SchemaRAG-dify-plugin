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

Usa o mesmo binário **dify-plugin** que usas para `plugin package` ([releases do daemon](https://github.com/langgenius/dify-plugin-daemon/releases)):

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
./dify-plugin-linux-amd64 plugin package . -o lm_db_schema_rag-0.2.3.difypkg

# 2) Assinar (produz ficheiro com sufixo .signed.difypkg)
./dify-plugin-linux-amd64 signature sign lm_db_schema_rag-0.2.3.difypkg -p lm_db_schema_rag_signing.private.pem
```

Resultado típico: `lm_db_schema_rag-0.2.3.signed.difypkg`

**Verificar localmente** antes de publicar:

```bash
./dify-plugin-linux-amd64 signature verify lm_db_schema_rag-0.2.3.signed.difypkg -p lm_db_schema_rag_signing.public.pem
```

*(Sem `-p`, o CLI pode validar contra a chave do marketplace oficial — o teu pacote **não** passará.)*

---

## 4. Publicar o ficheiro **assinado**

- Anexa à GitHub Release o **`.signed.difypkg`** (ou renomeia para `.difypkg` se o Dify só filtrar por extensão — o importante é ser o blob **já assinado**).
- Se quiseres CI: após `plugin package`, corre `signature sign` com a privada vinda de um **secret** (nunca em claro no YAML).

---

## 5. Configurar o Dify (plugin daemon)

### 5.1 Colocar a chave **pública** onde o contentor vê

No projeto Docker do Dify, o volume típico é `docker/volumes/plugin_daemon` montado em **`/app/storage`** no serviço `plugin_daemon`.

```bash
mkdir -p docker/volumes/plugin_daemon/public_keys
cp lm_db_schema_rag_signing.public.pem docker/volumes/plugin_daemon/public_keys/
```

### 5.2 Variáveis de ambiente (exemplo)

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

## 6. Boas práticas

1. **Rotação:** novo par de chaves → atualizar `.public.pem` no servidor e re-assinar releases; podes manter duas públicas em `THIRD_PARTY_SIGNATURE_VERIFICATION_PUBLIC_KEYS` durante a transição.
2. **CI:** secret tipo `PLUGIN_SIGNING_PRIVATE_PEM` (conteúdo PEM completo); script que escreve para ficheiro temporário, assina, apaga o ficheiro no fim do job.
3. **Não** commits de `.private.pem`; `.gitignore` deve ignorar `*.private.pem`.
4. Alinha a versão do **dify-plugin** CLI com a do *plugin daemon* que corre no Dify, para evitar incompatibilidades de formato de assinatura.

---

## 7. Relação com `FORCE_VERIFYING_SIGNATURE=false`

- **`false`:** desliga exigência de assinatura (rápido, menos seguro para ambientes expostos).
- **Fluxo deste documento:** mantém verificação **ligada** e restringe a **pacotes assinados pelas tuas chaves** — é o caminho “seguro” para plugins próprios fora do marketplace oficial.
