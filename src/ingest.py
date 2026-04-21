"""Ingestão do PDF: carrega, divide em chunks e persiste embeddings no pgVector."""

from __future__ import annotations

import logging
import os
import sys
import uuid
from collections.abc import Iterable
from pathlib import Path

from langchain_community.document_loaders import PyPDFLoader
from langchain_core.documents import Document
from langchain_text_splitters import RecursiveCharacterTextSplitter

from cli_utils import prompt_provider
from settings import (
    CHUNK_OVERLAP,
    CHUNK_SIZE,
    build_vector_store,
    get_pdf_path,
    set_provider,
)

logger = logging.getLogger(__name__)

_METADATA_KEYS = ("source", "page", "start_index")
_NAMESPACE = uuid.UUID("6f1b5f6e-4b6b-4b7b-9b3a-1f0a4f7a9c31")


def _normalize_metadata(doc: Document, source: str) -> dict:
    metadata = {k: v for k, v in (doc.metadata or {}).items() if k in _METADATA_KEYS}
    metadata.setdefault("source", source)
    return metadata


def _deterministic_id(metadata: dict) -> str:
    raw = f"{metadata.get('source')}|{metadata.get('page')}|{metadata.get('start_index')}"
    return str(uuid.uuid5(_NAMESPACE, raw))


def _prepare_chunks(documents: Iterable[Document], source: str) -> tuple[list[Document], list[str]]:
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=CHUNK_SIZE,
        chunk_overlap=CHUNK_OVERLAP,
        add_start_index=True,
    )
    chunks = splitter.split_documents(list(documents))

    enriched: list[Document] = []
    ids: list[str] = []
    for chunk in chunks:
        metadata = _normalize_metadata(chunk, source=source)
        enriched.append(Document(page_content=chunk.page_content, metadata=metadata))
        ids.append(_deterministic_id(metadata))
    return enriched, ids


def ingest_pdf() -> int:
    pdf_path = get_pdf_path()
    resolved = Path(pdf_path).expanduser().resolve()
    if not resolved.is_file():
        raise FileNotFoundError(f"PDF não encontrado em: {resolved}")

    logger.info("Carregando PDF de %s", resolved)
    documents = PyPDFLoader(str(resolved)).load()
    logger.info("Páginas carregadas: %d", len(documents))

    chunks, ids = _prepare_chunks(documents, source=resolved.name)
    if not chunks:
        logger.warning("Nenhum chunk gerado a partir do PDF.")
        return 0

    logger.info("Chunks gerados: %d (size=%d, overlap=%d)", len(chunks), CHUNK_SIZE, CHUNK_OVERLAP)

    store = build_vector_store()
    store.add_documents(documents=chunks, ids=ids)

    logger.info("Ingestão concluída: %d chunks persistidos no pgVector.", len(chunks))
    return len(chunks)


def _configure_logging() -> None:
    logging.basicConfig(
        level=os.getenv("LOG_LEVEL", "INFO").upper(),
        format="%(asctime)s %(levelname)s %(name)s - %(message)s",
    )


if __name__ == "__main__":
    _configure_logging()
    try:
        provider = prompt_provider()
        set_provider(provider)
        print(f"Provedor selecionado: {provider}\n")
        total = ingest_pdf()
        print(f"Ingestão concluída: {total} chunks persistidos.")
    except KeyboardInterrupt:
        print("\nIngestão cancelada pelo usuário.")
        sys.exit(130)
    except Exception as exc:
        logger.exception("Falha na ingestão: %s", exc)
        sys.exit(1)
