# Ingestão e Busca Semântica com LangChain e Postgres

Projeto do desafio do MBA — Engenharia de Software com IA (Full Cycle).

Aplicação em Python + LangChain que:

1. **Ingere** um arquivo PDF, dividindo-o em chunks e persistindo seus embeddings em PostgreSQL com extensão **pgVector**.
2. **Responde perguntas** via CLI baseando-se **exclusivamente** no conteúdo do PDF (RAG).

Suporta dois provedores de IA configuráveis: **OpenAI** e **Google Gemini**. A escolha é feita **interativamente** no início de cada execução (com pré-seleção opcional via `.env`).

---

## Estrutura

```
.
├── docker-compose.yml        # Postgres + extensão pgVector
├── requirements.txt          # Dependências Python (pinadas)
├── .env.example              # Template de variáveis de ambiente
├── Makefile                  # Atalhos: install/up/down/ingest/chat
├── document.pdf              # PDF a ser ingerido
├── src/
│   ├── settings.py           # Load de env, validação e factories
│   ├── cli_utils.py          # Prompt interativo de seleção de provedor
│   ├── ingest.py             # Script de ingestão do PDF
│   ├── search.py             # Busca semântica + chain do LLM
│   └── chat.py               # CLI de perguntas e respostas
└── README.md
```

---

## Pré-requisitos

- Python 3.12
- Docker e Docker Compose
- Chave de API do provedor escolhido:
  - **OpenAI**: `OPENAI_API_KEY`
  - **Gemini**: `GOOGLE_API_KEY`

---

## 1) Configurar ambiente

Crie e ative o virtualenv (`.venv` é o padrão do projeto e está no `.gitignore`) e instale as dependências:

```bash
python -m venv .venv

# Linux/macOS
source .venv/bin/activate
# Windows (PowerShell)
.\.venv\Scripts\Activate.ps1

python -m pip install --upgrade pip
pip install -r requirements.txt
```

> Reative o `.venv` a cada novo terminal. **Nunca** instale dependências no Python global.

Copie o arquivo de exemplo e preencha as credenciais:

```bash
cp .env.example .env
```

Edite `.env` e ajuste:

```env
# PROVIDER é OPCIONAL — serve só como pré-seleção do prompt interativo.
# Valores: openai | gemini
PROVIDER=openai

OPENAI_API_KEY=sk-...
OPENAI_EMBEDDING_MODEL=text-embedding-3-small

GOOGLE_API_KEY=...
GOOGLE_EMBEDDING_MODEL=gemini-embedding-2-preview

DATABASE_URL=postgresql+psycopg://postgres:postgres@localhost:5432/rag
PG_VECTOR_COLLECTION_NAME=documents

PDF_PATH=./document.pdf
```

> **Importante**: o `DATABASE_URL` **precisa** usar o driver `postgresql+psycopg://` (psycopg v3).

---

## 2) Subir o banco

```bash
docker compose up -d
```

O compose sobe o `postgres_rag` (imagem `pgvector/pgvector:pg17`) e um job auxiliar que executa `CREATE EXTENSION IF NOT EXISTS vector;`.

Verifique saúde:

```bash
docker compose ps
docker compose logs -f postgres
```

---

## 3) Ingestão do PDF

```bash
python src/ingest.py
```

Ao iniciar, o script **pergunta qual provedor usar**:

```
Selecione o provedor de IA:
  [1] OpenAI (default)
  [2] Gemini
Opção [1]:
```

Pressione **Enter** para aceitar o default (ou o valor de `PROVIDER` do `.env`), ou digite `1`/`openai` / `2`/`gemini`.

Em seguida o script:

- Carrega `document.pdf` com `PyPDFLoader`.
- Divide com `RecursiveCharacterTextSplitter(chunk_size=1000, chunk_overlap=150, add_start_index=True)`.
- Enriquece metadados (`source`, `page`, `start_index`).
- Gera **IDs determinísticos** (UUID v5) para permitir **re-ingestão idempotente**.
- Persiste os embeddings no pgVector via `PGVector.add_documents(documents, ids)`.

---

## 4) Executar o chat

```bash
python src/chat.py
```

O chat também começa pedindo o provedor (use o **mesmo** escolhido na ingestão — ver seção "Trocando de provedor").

Exemplo de interação:

```
Selecione o provedor de IA:
  [1] OpenAI (default)
  [2] Gemini
Opção [1]:
Provedor selecionado: openai

Chat iniciado. Digite sua pergunta ou 'sair' para encerrar.

PERGUNTA: Qual o faturamento da Empresa SuperTechIABrazil?
RESPOSTA: O faturamento foi de 10 milhões de reais.

PERGUNTA: Quantos clientes temos em 2024?
RESPOSTA: Não tenho informações necessárias para responder sua pergunta.

PERGUNTA: sair
Encerrando chat. Até logo!
```

Comandos de saída suportados: `exit`, `sair`, `quit`, `q` (ou `Ctrl+C`).

---

## Atalhos via Makefile

```bash
make install       # instala dependências de runtime
make install-dev   # instala runtime + dev e registra pre-commit
make up            # sobe docker compose
make ingest        # roda a ingestão (pergunta o provider)
make chat          # abre o chat (pergunta o provider)
make down          # derruba o banco
make clean         # derruba e REMOVE o volume (apaga embeddings)

# Qualidade de código
make lint          # Ruff (check)
make lint-fix      # Ruff com --fix
make fmt           # Ruff format
make fmt-check     # Ruff format --check
make typecheck     # mypy src/
make test          # pytest (quando houver testes)

# pre-commit
make precommit-install   # instala os hooks no .git/hooks
make precommit-run       # roda todos os hooks em todos os arquivos
make precommit-update    # autoupdate das revs dos hooks
```

---

## Desenvolvimento & qualidade de código

O projeto usa **Ruff** (lint + format), **mypy**, **pytest** e **pre-commit** como stack de qualidade. Toda a configuração vive em `pyproject.toml`. Os hooks rodam localmente antes do `git commit` e validam também a mensagem do commit (padrão Conventional Commits via commitizen).

### Setup inicial (uma vez)

Com o `.venv` ativo:

```bash
pip install -r requirements-dev.txt
pre-commit install --install-hooks
pre-commit install --hook-type commit-msg
```

Ou simplesmente `make install-dev`, que encadeia os três passos.

### Rotina diária

```bash
# Antes de abrir PR, rode tudo o que os hooks checariam:
make precommit-run

# Ou, de forma granular:
make lint-fix   # corrige imports/estilo automaticamente
make fmt        # formata
make typecheck  # mypy
```

### Hooks configurados (`.pre-commit-config.yaml`)

| Hook | Ação |
|---|---|
| `pre-commit-hooks` | whitespace, EOF, YAML/TOML/JSON válido, sem merge markers, sem chaves privadas, EOL LF |
| `ruff-check --fix` | lint + correções automáticas (isort, pyupgrade, bugbear, bandit, pathlib etc.) |
| `ruff-format` | formatação estilo Black |
| `gitleaks` | varre segredos (API keys, tokens) no diff |
| `commitizen` (commit-msg) | valida mensagem no padrão Conventional Commits (`feat`, `fix`, `docs`, …) |

> Segredos em `.env` ficam protegidos por duas camadas: `.gitignore` + `gitleaks` + `detect-private-key`. **Nunca** remova `.env` do `.gitignore`.

### Convenções de commit

Mensagens seguem **Conventional Commits** em pt-BR:

```
feat(ingest): adiciona IDs determinísticos para re-ingestão idempotente
fix(search): corrige prompt quando contexto vem vazio
chore(deps): atualiza langchain para 0.3.27
```

Tipos comuns: `feat`, `fix`, `chore`, `refactor`, `docs`, `test`, `perf`, `ci`.

---

## Como funciona a busca (RAG)

1. A pergunta do usuário é vetorizada com o mesmo modelo de embeddings usado na ingestão.
2. Recupera-se os **10 trechos mais similares** via `similarity_search_with_score(query, k=10)`.
3. Os trechos são concatenados no placeholder `{contexto}` do prompt.
4. O LLM responde seguindo regras estritas: se a informação não estiver no contexto, responde `"Não tenho informações necessárias para responder sua pergunta."`

---

## Trocando de provedor (OpenAI ⇄ Gemini)

As dimensões dos embeddings são **diferentes** entre provedores (OpenAI `text-embedding-3-small` = 1536; Gemini `gemini-embedding-2-preview` = 3072 por padrão, configurável via `output_dimensionality`). **Sempre** use o mesmo provedor na ingestão e na busca. Ao trocar, faça uma das duas opções:

**Opção A — limpar o banco e reingerir:**

```bash
docker compose down -v
docker compose up -d
python src/ingest.py   # selecione o novo provedor
```

**Opção B — usar coleções distintas:** altere `PG_VECTOR_COLLECTION_NAME` no `.env` (ex.: `documents_openai`, `documents_gemini`) antes de reingerir com cada provedor.

---

## Troubleshooting

- **`langchain_postgres` erro de conexão**: confirme o prefixo `postgresql+psycopg://` no `DATABASE_URL` e que o container do Postgres está saudável (`docker compose ps`).
- **`PDF_PATH` não encontrado**: o caminho é relativo ao diretório onde você executa o script. Prefira caminho absoluto em `.env`.
- **Respostas sempre "Não tenho informações..."**: verifique se a ingestão rodou (olhar logs) e se selecionou o mesmo provedor usado na ingestão.
- **Erro de dimensão ao buscar**: você mudou de provedor sem limpar a collection — ver seção anterior.

---

## Tecnologias

- Python 3.12, LangChain (`langchain`, `langchain-core`, `langchain-community`, `langchain-text-splitters`)
- `langchain-postgres` (PGVector) + `psycopg` v3
- `langchain-openai` e `langchain-google-genai`
- PostgreSQL 17 com extensão `pgvector` (via Docker)
