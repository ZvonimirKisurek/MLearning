"""FastAPI dependencies: settings, the async DB pool, per-request connections, auth, task queue.

WHY ASYNC?  FastAPI runs on an event loop: one thread juggles many in-flight requests. A request that awaits
the database *yields* the thread, so while Postgres works on query A the loop serves request B. A blocking
(sync) driver would freeze the loop for every other client for the duration of each query. `psycopg`'s
AsyncConnectionPool gives us true non-blocking I/O. (Celery workers and the CLI keep using the sync pool in
app/db.py: they are single-job processes where blocking is fine.)

CONNECTION LIFECYCLE: one pool per process (opened/closed in `lifespan`), one *borrowed connection per request*.
`async with pool.connection()` is also a transaction: it COMMITs when the block exits cleanly and ROLLBACKs on an
exception - so a failing endpoint can never leave half-applied writes.
"""
from __future__ import annotations

import logging
import secrets
from collections.abc import AsyncIterator, Callable
from typing import Annotated

from fastapi import Depends, Header, HTTPException, Request, status
from psycopg import AsyncConnection
from psycopg.rows import dict_row
from psycopg_pool import AsyncConnectionPool
from pgvector.psycopg import register_vector_async

from app.config import Settings, get_settings

log = logging.getLogger(__name__)


async def _configure(conn: AsyncConnection) -> None:
    await conn.execute("SET search_path TO public, extensions")  # Supabase keeps `vector` in `extensions`
    await conn.commit()
    await register_vector_async(conn)


def build_pool(settings: Settings) -> AsyncConnectionPool:
    return AsyncConnectionPool(
        settings.database_url, min_size=1, max_size=settings.db_pool_size, open=False, configure=_configure,
        # prepare_threshold=None keeps us compatible with PgBouncer/Supavisor transaction pooling.
        kwargs={"row_factory": dict_row, "prepare_threshold": None},
    )


def settings_dep() -> Settings:  # a function (not a constant) so tests can override it via app.dependency_overrides
    return get_settings()


def get_pool(request: Request) -> AsyncConnectionPool:
    return request.app.state.pool


async def get_conn(pool: Annotated[AsyncConnectionPool, Depends(get_pool)]) -> AsyncIterator[AsyncConnection]:
    async with pool.connection() as conn:
        yield conn


# scope="function": the dependency's teardown (= COMMIT) runs right after the endpoint function returns and
# BEFORE the response is sent. With the default scope, newer FastAPI versions run teardown after sending, so a
# client could receive "200 OK" and immediately read data that is not committed yet (read-after-write race).
Conn = Annotated[AsyncConnection, Depends(get_conn, scope="function")]
Cfg = Annotated[Settings, Depends(settings_dep)]


async def require_token(settings: Cfg, authorization: Annotated[str | None, Header()] = None) -> None:
    """Single-user bearer auth. The browser never sees this token: Next.js calls the API from the server."""
    if not settings.api_token:
        return  # open (development). Set API_TOKEN in production.
    scheme, _, token = (authorization or "").partition(" ")
    if scheme.lower() != "bearer" or not secrets.compare_digest(token.encode(), settings.api_token.encode()):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "invalid or missing token", headers={"WWW-Authenticate": "Bearer"})


def get_enqueue() -> Callable[[str], None]:
    """Returns a function that enqueues a Celery task by name (no import of the task code into the API process)."""
    def enqueue(task_name: str) -> None:
        from app.celery_app import app as celery

        # Pre-flight: kombu retries a dead broker connection for a long time by default (~20s). Probe once with a
        # short timeout so a missing Redis surfaces as a quick 503, not a hung request.
        with celery.connection_for_write() as conn:
            conn.ensure_connection(max_retries=1, interval_start=0, interval_step=0.2, timeout=2)
        celery.send_task(task_name, retry=False)
    return enqueue
