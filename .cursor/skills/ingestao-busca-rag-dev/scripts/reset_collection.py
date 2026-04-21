"""Remove a collection PGVector para permitir re-ingestão do zero.

Uso típico: quando trocar PROVIDER (ex.: openai ↔ gemini) a dimensão do
embedding muda e o índice existente fica incompatível.

Uso:
    python .cursor/skills/ingestao-busca-rag-dev/scripts/reset_collection.py
    python .cursor/skills/ingestao-busca-rag-dev/scripts/reset_collection.py --yes

Exit 0 = OK; 1 = falha ou cancelado.
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

try:
    import psycopg
    from dotenv import load_dotenv
except ImportError as exc:
    print(
        f"ERRO: dependência ausente ({exc}). "
        "Ative o .venv e rode: pip install -r requirements.txt"
    )
    sys.exit(1)


def _to_psycopg_url(sqlalchemy_url: str) -> str:
    return sqlalchemy_url.replace("postgresql+psycopg://", "postgresql://", 1)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--yes",
        "-y",
        action="store_true",
        help="Pula a confirmação interativa.",
    )
    parser.add_argument(
        "--collection",
        default=None,
        help="Sobrescreve a collection (default: PG_VECTOR_COLLECTION_NAME do .env).",
    )
    args = parser.parse_args()

    repo_root = Path(__file__).resolve().parents[4]
    load_dotenv(repo_root / ".env", override=True)

    url = os.getenv("DATABASE_URL", "").strip()
    if not url:
        print("ERRO: DATABASE_URL não definido.", file=sys.stderr)
        return 1

    collection = (
        args.collection
        or os.getenv("PG_VECTOR_COLLECTION_NAME", "").strip()
    )
    if not collection:
        print("ERRO: PG_VECTOR_COLLECTION_NAME não definido.", file=sys.stderr)
        return 1

    if not args.yes:
        print(f"Isto removerá TODA a collection '{collection}' e seus embeddings.")
        resp = input("Confirma? [y/N]: ").strip().lower()
        if resp not in {"y", "yes", "s", "sim"}:
            print("Cancelado.")
            return 1

    try:
        with psycopg.connect(_to_psycopg_url(url), connect_timeout=5) as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT uuid FROM langchain_pg_collection WHERE name = %s;",
                    (collection,),
                )
                row = cur.fetchone()
                if row is None:
                    print(f"Collection '{collection}' não existe. Nada a fazer.")
                    return 0

                coll_uuid = row[0]
                cur.execute(
                    "DELETE FROM langchain_pg_embedding WHERE collection_id = %s;",
                    (coll_uuid,),
                )
                deleted_embeddings = cur.rowcount
                cur.execute(
                    "DELETE FROM langchain_pg_collection WHERE uuid = %s;",
                    (coll_uuid,),
                )
                conn.commit()

    except Exception as exc:
        print(f"ERRO durante reset: {exc}", file=sys.stderr)
        return 1

    print(
        f"Collection '{collection}' removida "
        f"({deleted_embeddings} embeddings apagados)."
    )
    print("Rode 'python src/ingest.py' para reconstruir o índice.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
