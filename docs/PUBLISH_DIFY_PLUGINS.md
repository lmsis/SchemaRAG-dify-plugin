# Publicar o pacote no ecossistema `dify-plugins`

Os workflows **Plugin Publish Workflow** e **Auto Create PR on Main Push** precisam de um **fork** do repositório oficial.

## 1. Criar o fork

1. Abre <https://github.com/langgenius/dify-plugins>
2. **Fork** para a tua conta ou organização GitHub
3. O repositório resultante **deve** chamar-se `dify-plugins` (padrão ao fazer fork)

Se o fork ficar em `https://github.com/ACCOUNT/dify-plugins`, o GitHub passa a expor o repo como **`ACCOUNT/dify-plugins`**.

## 2. Alinhar com o `manifest.yaml`

- O campo **`author`** no `manifest` (ex.: `lmsis`) define a pasta do pacote dentro do monorepo: `author/nome_do_plugin/*.difypkg`.
- O **dono do fork no GitHub** pode ser outro (ex.: utilizador pessoal) enquanto o `author` no manifest continua a ser o identificador do plugin.

Se o fork **não** estiver em `{author}/dify-plugins`, define o secret **`DIFY_PLUGINS_FORK`** (ex.: `minha-conta/dify-plugins`).

## 3. Secrets no repositório do plugin

| Secret | Obrigatório | Descrição |
|--------|-------------|-----------|
| **`PLUGIN_ACTION`** | Recomendado | PAT (classic) com scope **`repo`**, da conta que tem push no fork e pode abrir PR para `langgenius/dify-plugins`. |
| **`DIFY_PLUGINS_FORK`** | Opcional | `owner/dify-plugins` se o fork não for `{manifest author}/dify-plugins`. |

Sem **`PLUGIN_ACTION`**, o checkout pode usar `GITHUB_TOKEN`, mas **push** e **`gh pr create`** costumam falhar.

## 4. Erro `Not Found` no checkout

Significa que o repo `OWNER/dify-plugins` não existe, está privado sem acesso ao token, ou o `OWNER` está errado. Corrige criando o fork ou ajustando **`DIFY_PLUGINS_FORK`**.
