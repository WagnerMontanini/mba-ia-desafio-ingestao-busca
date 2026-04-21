"""Valida o arquivo .env contra o provider configurado.

Uso:
    python .cursor/skills/ingestao-busca-rag-dev/scripts/check_env.py

Retorna exit code 0 se tudo válido; 1 caso contrário.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

try:
    from dotenv import load_dotenv
except ImportError:
    print(
        "ERRO: python-dotenv não instalado. Ative o .venv e rode:\n"
        "    pip install -r requirements.txt\n"
        "Se ainda não criou o venv: python -m venv .venv && "
        ".\\.venv\\Scripts\\Activate.ps1 (Windows) ou source .venv/bin/activate (Unix).",
        file=sys.stderr,
    )
    sys.exit(1)


REQUIRED_BASE = (
    "PROVIDER",
    "DATABASE_URL",
    "PG_VECTOR_COLLECTION_NAME",
    "PDF_PATH",
)

REQUIRED_BY_PROVIDER = {
    "openai": ("OPENAI_API_KEY",),
    "gemini": ("GOOGLE_API_KEY",),
}


def _check_var(name: str, errors: list[str]) -> str | None:
    value = os.getenv(name)
    if value is None or not str(value).strip():
        errors.append(f"- {name} ausente ou vazio")
        return None
    return str(value).strip()


def main() -> int:
    repo_root = Path(__file__).resolve().parents[4]
    env_path = repo_root / ".env"
    if not env_path.is_file():
        print(
            f"ERRO: .env não encontrado em {env_path}. "
            "Copie .env.example para .env e preencha.",
            file=sys.stderr,
        )
        return 1

    load_dotenv(env_path, override=True)

    errors: list[str] = []

    for name in REQUIRED_BASE:
        _check_var(name, errors)

    provider = os.getenv("PROVIDER", "").strip().lower()
    if provider not in REQUIRED_BY_PROVIDER:
        errors.append(
            f"- PROVIDER inválido: {provider!r}. Use 'openai' ou 'gemini'."
        )
    else:
        for name in REQUIRED_BY_PROVIDER[provider]:
            _check_var(name, errors)

    database_url = os.getenv("DATABASE_URL", "")
    if database_url and not database_url.startswith("postgresql+psycopg://"):
        errors.append(
            f"- DATABASE_URL deve usar driver psycopg3 "
            f"(prefixo 'postgresql+psycopg://'). Atual: {database_url!r}"
        )

    pdf_path = os.getenv("PDF_PATH", "")
    if pdf_path:
        pdf_full = (repo_root / pdf_path).resolve()
        if not pdf_full.is_file():
            errors.append(f"- PDF_PATH aponta para arquivo inexistente: {pdf_full}")

    if errors:
        print("FALHA — problemas encontrados no .env:", file=sys.stderr)
        for e in errors:
            print(e, file=sys.stderr)
        return 1

    print(f"OK — env válido para provider={provider}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
