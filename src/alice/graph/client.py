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
