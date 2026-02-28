"""Neo4j driver wrapper — connection pool, query execution, schema bootstrapping."""

from __future__ import annotations

from typing import Any, Protocol, cast

import structlog
from neo4j import AsyncDriver, AsyncGraphDatabase

from alice.graph.schema import SCHEMA_STATEMENTS


class _Logger(Protocol):
    def info(self, event: str, **kw: object) -> None: ...
    def error(self, event: str, **kw: object) -> None: ...
    def debug(self, event: str, **kw: object) -> None: ...


logger = cast(_Logger, structlog.get_logger(__name__))


# ── Edge ID helpers ────────────────────────────────────────────────────────────
# Use '::' as separator so concept names containing '-' won't break parsing.
EDGE_ID_SEP = "::"


def make_edge_id(source: str, relation: str, target: str) -> str:
    """Build a deterministic edge identifier: source::RELATION::target."""
    return f"{source}{EDGE_ID_SEP}{relation}{EDGE_ID_SEP}{target}"


def parse_edge_id(edge_id: str) -> tuple[str, str, str]:
    """Parse an edge ID into (source, relation, target).

    Raises ValueError if the format is invalid.
    Supports both new '::' separator and legacy '-' separator for backward compat.
    """
    if EDGE_ID_SEP in edge_id:
        parts = edge_id.split(EDGE_ID_SEP)
        if len(parts) != 3:
            raise ValueError(f"Invalid edge_id format: {edge_id!r}")
        return parts[0], parts[1], parts[2]

    # Legacy format: 'source-RELATION_TYPE-target' (split from right to handle names with -)
    # Heuristic: relation types are UPPER_SNAKE_CASE
    import re
    match = re.match(r'^(.+?)-([A-Z_]+)-(.+)$', edge_id)
    if not match:
        raise ValueError(f"Invalid edge_id format: {edge_id!r}")
    return match.group(1), match.group(2), match.group(3)


class GraphClient:
    """Async Neo4j driver wrapper with connection pool and schema bootstrap."""

    def __init__(self, uri: str, auth: tuple[str, str]) -> None:
        self._uri = uri
        self._auth = auth
        self._driver: AsyncDriver | None = None

    async def connect(self) -> None:
        """Open the driver (creates connection pool)."""
        self._driver = AsyncGraphDatabase.driver(self._uri, auth=self._auth)
        logger.info("neo4j_connected", uri=self._uri)

    async def close(self) -> None:
        """Close the driver and release pool."""
        if self._driver:
            await self._driver.close()
            self._driver = None
            logger.info("neo4j_closed")

    async def __aenter__(self) -> GraphClient:
        await self.connect()
        return self

    async def __aexit__(self, *_: object) -> None:
        await self.close()

    @property
    def connected(self) -> bool:
        return self._driver is not None

    async def health_check(self) -> bool:
        """Return True if Neo4j is reachable."""
        if not self._driver:
            return False
        try:
            await self._driver.verify_connectivity()
            return True
        except Exception:
            return False

    async def execute_query(
        self,
        cypher: str,
        parameters: dict[str, Any] | None = None,
    ) -> list[dict[str, Any]]:
        """Execute a Cypher query and return list of record dicts."""
        if not self._driver:
            raise RuntimeError("GraphClient not connected — call connect() first")
        async with self._driver.session() as session:
            result = await session.run(cypher, parameters or {})
            records = await result.data()
            logger.debug("cypher_executed", cypher=cypher[:80], rows=len(records))
            return records

    async def ensure_schema(self) -> None:
        """Create constraints and indexes (idempotent — IF NOT EXISTS)."""
        for stmt in SCHEMA_STATEMENTS:
            await self.execute_query(stmt)
        logger.info("neo4j_schema_ensured", statements=len(SCHEMA_STATEMENTS))


# ── Application-wide singleton ─────────────────────────────────────────────────
_shared_client: GraphClient | None = None


async def get_shared_graph_client(uri: str, auth: tuple[str, str]) -> GraphClient:
    """Return (and lazily create) a shared GraphClient singleton.

    Call close_shared_graph_client() on shutdown.
    """
    global _shared_client
    if _shared_client is None or not _shared_client.connected:
        _shared_client = GraphClient(uri, auth)
        await _shared_client.connect()
    return _shared_client


async def close_shared_graph_client() -> None:
    """Gracefully close the shared client on application shutdown."""
    global _shared_client
    if _shared_client is not None:
        await _shared_client.close()
        _shared_client = None
