# Snippets verificados

Trechos prontos para colar e adaptar. Compatíveis com as versões fixadas em `requirements.txt`:
- `langchain==0.3.27`, `langchain-core==0.3.74`
- `langchain-postgres==0.0.15`
- `langchain-text-splitters==0.3.9`
- `langchain-community==0.3.27`, `pypdf==6.0.0`
- `psycopg==3.2.9`

## 1. `src/ingest.py` completo (referência)

```python
"""Pipeline de ingestão: PDF → chunks → embeddings → PGVector."""

from __future__ import annotations

import logging
import os
import uuid
from pathlib import Path

from langchain_community.document_loaders import PyPDFLoader
from langchain_core.documents import Document
from langchain_text_splitters import RecursiveCharacterTextSplitter

from settings import CHUNK_OVERLAP, CHUNK_SIZE, build_vector_store, get_pdf_path

logger = logging.getLogger(__name__)

_NAMESPACE = uuid.UUID("6ba7b810-9dad-11d1-80b4-00c04fd430c8")
_KEEP_META = {"source", "page", "start_index"}


def _chunk_id(source: str, page: int, start_index: int) -> str:
    return str(uuid.uuid5(_NAMESPACE, f"{source}|{page}|{start_index}"))


def _slim_metadata(doc: Document) -> Document:
    meta = {k: v for k, v in doc.metadata.items() if k in _KEEP_META}
    return Document(page_content=doc.page_content, metadata=meta)


def ingest_pdf() -> int:
    """Carrega, fragmenta e persiste o PDF configurado.

    Returns:
        Quantidade de chunks persistidos.
    """
    pdf_path = get_pdf_path()
    if not Path(pdf_path).is_file():
        raise FileNotFoundError(f"PDF não encontrado em: {pdf_path}")

    logger.info("Iniciando ingestão de %s", pdf_path)

    raw_docs = PyPDFLoader(pdf_path).load()
    logger.info("PDF carregado: %d páginas", len(raw_docs))

    splitter = RecursiveCharacterTextSplitter(
        chunk_size=CHUNK_SIZE,
        chunk_overlap=CHUNK_OVERLAP,
        add_start_index=True,
    )
    chunks = [
        _slim_metadata(c)
        for c in splitter.split_documents(raw_docs)
        if c.page_content.strip()
    ]
    if not chunks:
        logger.warning("Nenhum chunk gerado — ingestão abortada.")
        return 0

    ids = [
        _chunk_id(
            source=str(c.metadata.get("source", pdf_path)),
            page=int(c.metadata.get("page", 0)),
            start_index=int(c.metadata.get("start_index", 0)),
        )
        for c in chunks
    ]

    store = build_vector_store()
    store.add_documents(documents=chunks, ids=ids)

    logger.info("Ingestão concluída: %d chunks persistidos.", len(chunks))
    return len(chunks)


if __name__ == "__main__":
    logging.basicConfig(
        level=os.getenv("LOG_LEVEL", "INFO"),
        format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
    )
    ingest_pdf()
```

## 2. `src/search.py` completo (referência)

```python
"""Busca vetorial + chain LCEL restrita ao contexto recuperado."""

from __future__ import annotations

from typing import Callable

from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import PromptTemplate

from settings import TOP_K, build_vector_store, get_llm

PROMPT_TEMPLATE = """
CONTEXTO:
{contexto}

REGRAS:
- Responda somente com base no CONTEXTO.
- Se a informação não estiver explicitamente no CONTEXTO, responda:
  "Não tenho informações necessárias para responder sua pergunta."
- Nunca invente ou use conhecimento externo.
- Nunca produza opiniões ou interpretações além do que está escrito.

EXEMPLOS DE PERGUNTAS FORA DO CONTEXTO:
Pergunta: "Qual é a capital da França?"
Resposta: "Não tenho informações necessárias para responder sua pergunta."

Pergunta: "Quantos clientes temos em 2024?"
Resposta: "Não tenho informações necessárias para responder sua pergunta."

Pergunta: "Você acha isso bom ou ruim?"
Resposta: "Não tenho informações necessárias para responder sua pergunta."

PERGUNTA DO USUÁRIO:
{pergunta}

RESPONDA A "PERGUNTA DO USUÁRIO"
"""


def search_prompt() -> Callable[[str], str]:
    """Constrói um callable `ask(question)` que consulta o índice e chama o LLM."""
    store = build_vector_store()
    prompt = PromptTemplate(
        template=PROMPT_TEMPLATE,
        input_variables=["contexto", "pergunta"],
    )
    chain = prompt | get_llm() | StrOutputParser()

    def ask(question: str) -> str:
        docs = store.similarity_search_with_score(question, k=TOP_K)
        contexto = "\n\n".join(d.page_content.strip() for d, _ in docs)
        return chain.invoke({"contexto": contexto, "pergunta": question}).strip()

    return ask
```

## 3. `src/chat.py` completo (referência)

```python
"""REPL de perguntas e respostas sobre o índice vetorial."""

from __future__ import annotations

import logging
import sys

from search import search_prompt

BANNER = (
    "Chat RAG iniciado. Digite sua pergunta e pressione Enter.\n"
    "Digite 'exit' ou 'sair' (ou Ctrl+C) para encerrar.\n"
)
EXIT_CMDS = {"exit", "sair", "quit"}


def main() -> int:
    logging.basicConfig(level=logging.WARNING, format="%(levelname)s: %(message)s")

    try:
        ask = search_prompt()
    except Exception as exc:
        print(f"Falha ao inicializar o chat: {exc}", file=sys.stderr)
        return 1

    print(BANNER)
    while True:
        try:
            question = input("PERGUNTA: ").strip()
        except (KeyboardInterrupt, EOFError):
            print()
            break

        if not question:
            continue
        if question.lower() in EXIT_CMDS:
            break

        try:
            answer = ask(question)
        except Exception:
            logging.exception("Erro ao processar pergunta")
            continue

        print(f"\nRESPOSTA: {answer}\n")

    print("Até a próxima.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
```

## 4. `.env.example` completo (referência)

```dotenv
# Provider ativo: openai | gemini
PROVIDER=openai

# Credenciais OpenAI (usadas quando PROVIDER=openai)
OPENAI_API_KEY=
OPENAI_EMBEDDING_MODEL=text-embedding-3-small

# Credenciais Google Gemini (usadas quando PROVIDER=gemini)
GOOGLE_API_KEY=
GOOGLE_EMBEDDING_MODEL=gemini-embedding-2-preview

# Banco vetorial (driver psycopg3 obrigatório)
DATABASE_URL=postgresql+psycopg://postgres:postgres@localhost:5432/rag
PG_VECTOR_COLLECTION_NAME=documents

# Arquivo a ser ingerido
PDF_PATH=./document.pdf
```

## 5. Invocação one-shot (sem REPL) para smoke test

```python
# scripts/sanity.py (não commit)
from src.search import search_prompt

ask = search_prompt()
print(ask("Do que trata o documento?"))
print(ask("Qual é a capital da França?"))  # deve cair no fallback
```

## 6. Contagem de queries no Postgres (debug)

```sql
-- Ver collections existentes
SELECT uuid, name, cmetadata FROM langchain_pg_collection;

-- Ver embeddings por collection
SELECT c.name, COUNT(e.*) AS n
FROM langchain_pg_collection c
LEFT JOIN langchain_pg_embedding e ON e.collection_id = c.uuid
GROUP BY c.name;

-- Ver dimensão do vetor da primeira linha
SELECT array_length(embedding::real[], 1) AS dim
FROM langchain_pg_embedding
LIMIT 1;
```

## 7. Import patterns — armadilhas

```python
# ❌ ERRADO — classe depreciada
from langchain.vectorstores import PGVector

# ❌ ERRADO — esta é a classe antiga, sem use_jsonb
from langchain_community.vectorstores.pgvector import PGVector

# ✅ CORRETO
from langchain_postgres import PGVector
```

```python
# ❌ ERRADO — splitter depreciado
from langchain.text_splitter import RecursiveCharacterTextSplitter

# ✅ CORRETO
from langchain_text_splitters import RecursiveCharacterTextSplitter
```

## 8. Mensagens de commit sugeridas

```text
feat(env): documenta PROVIDER e modelos de referência no .env.example

feat(ingest): implementa pipeline PDF → PGVector com IDs determinísticos

- Carrega PDF via PyPDFLoader
- Chunking 1000/150 com add_start_index
- UUIDv5 estável (source|page|start_index) garante idempotência
- Metadata enxuta (source, page, start_index)

feat(search): adiciona search_prompt com chain LCEL top-k 10

feat(chat): cria REPL com exit/sair, Ctrl+C graceful e proteção de input vazio

chore(make): adiciona Makefile com up/down/ingest/chat/check/reset

docs(readme): documenta setup, providers, execução e troubleshooting
```
