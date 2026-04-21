"""Configuração centralizada: variáveis de ambiente, validação e factories."""

from __future__ import annotations

import os
from typing import Literal

from dotenv import load_dotenv
from langchain_core.embeddings import Embeddings
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_google_genai import ChatGoogleGenerativeAI, GoogleGenerativeAIEmbeddings
from langchain_openai import ChatOpenAI, OpenAIEmbeddings
from langchain_postgres import PGVector

load_dotenv()

CHUNK_SIZE = 1000
CHUNK_OVERLAP = 150
TOP_K = 10

ProviderLiteral = Literal["openai", "gemini"]

_VALID_PROVIDERS: tuple[ProviderLiteral, ...] = ("openai", "gemini")
_PROVIDER_OVERRIDE: ProviderLiteral | None = None


def _require_env(name: str) -> str:
    value = os.getenv(name)
    if value is None or not str(value).strip():
        raise RuntimeError(
            f"Variável de ambiente obrigatória ausente ou vazia: {name}. "
            "Copie .env.example para .env e preencha os valores."
        )
    return str(value).strip()


def set_provider(provider: str) -> ProviderLiteral:
    """Define explicitamente o provedor ativo (override em memória).

    Tem prioridade sobre a variável de ambiente ``PROVIDER`` e é usada
    pelos scripts CLI (``ingest.py``, ``chat.py``) após o prompt
    interativo de seleção.
    """
    global _PROVIDER_OVERRIDE
    normalized = (provider or "").strip().lower()
    if normalized not in _VALID_PROVIDERS:
        raise RuntimeError(f"PROVIDER inválido: {provider!r}. Use 'openai' ou 'gemini'.")
    _PROVIDER_OVERRIDE = normalized  # type: ignore[assignment]
    return _PROVIDER_OVERRIDE  # type: ignore[return-value]


def get_provider() -> ProviderLiteral:
    if _PROVIDER_OVERRIDE is not None:
        return _PROVIDER_OVERRIDE
    raw = os.getenv("PROVIDER", "openai").strip().lower()
    if raw not in _VALID_PROVIDERS:
        raise RuntimeError(f"PROVIDER inválido: {raw!r}. Use 'openai' ou 'gemini'.")
    return raw  # type: ignore[return-value]


def validate_provider_credentials(provider: ProviderLiteral) -> None:
    if provider == "openai":
        _require_env("OPENAI_API_KEY")
    else:
        _require_env("GOOGLE_API_KEY")


def get_database_url() -> str:
    return _require_env("DATABASE_URL")


def get_collection_name() -> str:
    return _require_env("PG_VECTOR_COLLECTION_NAME")


def get_pdf_path() -> str:
    return _require_env("PDF_PATH")


def get_embeddings() -> Embeddings:
    provider = get_provider()
    validate_provider_credentials(provider)
    if provider == "openai":
        model = os.getenv("OPENAI_EMBEDDING_MODEL", "text-embedding-3-small").strip()
        return OpenAIEmbeddings(model=model)
    model = os.getenv("GOOGLE_EMBEDDING_MODEL", "gemini-embedding-2-preview").strip()
    return GoogleGenerativeAIEmbeddings(model=model)


def get_llm() -> BaseChatModel:
    provider = get_provider()
    validate_provider_credentials(provider)
    if provider == "openai":
        return ChatOpenAI(model="gpt-5-nano", temperature=0)
    return ChatGoogleGenerativeAI(model="gemini-2.5-flash-lite", temperature=0)


def build_vector_store() -> PGVector:
    """Instância PGVector compartilhando embeddings e conexão configurados."""
    return PGVector(
        embeddings=get_embeddings(),
        collection_name=get_collection_name(),
        connection=get_database_url(),
        use_jsonb=True,
    )
