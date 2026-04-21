"""Verifica conexão com o Postgres e presença da extensão pgvector.

Uso:
    python .cursor/skills/ingestao-busca-rag-dev/scripts/verify_db.py

Exit code 0 = OK; 1 = falha.
"""

from __future__ import annotations

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
    """Converte URL SQLAlchemy (postgresql+psycopg://) para formato psycopg puro."""
    return sqlalchemy_url.replace("postgresql+psycopg://", "postgresql://", 1)


def main() -> int:
    repo_root = Path(__file__).resolve().parents[4]
    load_dotenv(repo_root / ".env", override=True)

    url = os.getenv("DATABASE_URL", "").strip()
    if not url:
        print("ERRO: DATABASE_URL não definido.", file=sys.stderr)
        return 1

    collection = os.getenv("PG_VECTOR_COLLECTION_NAME", "").strip() or "(não definido)"

    conn_url = _to_psycopg_url(url)

    try:
        with psycopg.connect(conn_url, connect_timeout=5) as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT version();")
                version = cur.fetchone()[0]

                cur.execute(
                    "SELECT extname FROM pg_extension WHERE extname = 'vector';"
                )
                has_vector = cur.fetchone() is not None

                cur.execute(
                    """
                    SELECT table_name
                      FROM information_schema.tables
                     WHERE table_schema = 'public'
                       AND table_name IN (
                         'langchain_pg_collection',
                         'langchain_pg_embedding'
                       );
                    """
                )
                tables = {row[0] for row in cur.fetchall()}

                collection_exists = False
                embedding_count = None
                if "langchain_pg_collection" in tables:
                    cur.execute(
                        "SELECT uuid FROM langchain_pg_collection WHERE name = %s;",
                        (collection,),
                    )
                    row = cur.fetchone()
                    if row:
                        collection_exists = True
                        cur.execute(
                            "SELECT COUNT(*) FROM langchain_pg_embedding "
                            "WHERE collection_id = %s;",
                            (row[0],),
                        )
                        embedding_count = cur.fetchone()[0]

    except Exception as exc:
        print(f"ERRO de conexão: {exc}", file=sys.stderr)
        return 1

    print("Conexão: OK")
    print(f"Versão: {version.splitlines()[0]}")
    print(f"Extensão pgvector: {'instalada' if has_vector else 'AUSENTE'}")
    print(f"Tabelas LangChain: {sorted(tables) or 'nenhuma ainda'}")
    print(f"Collection '{collection}': {'existe' if collection_exists else 'não existe'}")
    if embedding_count is not None:
        print(f"Embeddings na collection: {embedding_count}")

    if not has_vector:
        print(
            "AVISO: extensão 'vector' não está instalada. "
            "Rode: docker compose up -d  e aguarde o bootstrap_vector_ext.",
            file=sys.stderr,
        )
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
