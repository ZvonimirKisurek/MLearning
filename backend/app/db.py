from __future__ import annotations

from psycopg import Connection
from psycopg.rows import dict_row
from psycopg_pool import ConnectionPool
from pgvector.psycopg import register_vector

from app.config import get_settings

_pool: ConnectionPool | None = None


def _configure(conn: Connection) -> None:
    # Supabase installs extensions in the `extensions` schema; make `vector` resolvable on any Postgres.
    conn.execute("SET search_path TO public, extensions")
    conn.commit()
    register_vector(conn)


def get_pool() -> ConnectionPool:
    global _pool
    if _pool is None:
        _pool = ConnectionPool(
            get_settings().database_url,
            min_size=1,
            max_size=5,
            configure=_configure,
            # prepare_threshold=None: no server-side prepared statements => compatible with Supabase's
            # transaction-mode pooler (PgBouncer/Supavisor).
            kwargs={"row_factory": dict_row, "prepare_threshold": None},
            open=True,
        )
    return _pool
