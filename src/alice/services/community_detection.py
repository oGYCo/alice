"""Leiden community detection on the user knowledge graph.

Algorithm: Leiden via leidenalg (Python-side — NOT Neo4j GDS).
Pipeline:
  1. Export user KG from Neo4j → NetworkX DiGraph
  2. Convert to igraph undirected Graph
  3. Run leidenalg RBConfigurationVertexPartition
  4. Map communities back to concept names
  5. Write community_id property back to Neo4j concept nodes
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol, cast

import igraph
import leidenalg
import structlog

from alice.graph.client import GraphClient


class _Logger(Protocol):
    def info(self, event: str, **kw: object) -> None: ...
    def warning(self, event: str, **kw: object) -> None: ...
    def debug(self, event: str, **kw: object) -> None: ...


logger = cast(_Logger, structlog.get_logger(__name__))

# Leiden algorithm parameters
_LEIDEN_RESOLUTION = 1.0
_LEIDEN_SEED = 42

# A community is "sparse" when its mean mastery is below this threshold
_SPARSE_MASTERY_THRESHOLD = 0.35


@dataclass
class Community:
    """A detected cluster of related knowledge concepts."""

    community_id: int
    concepts: list[str]
    avg_mastery: float = 0.0
    label: str = ""

    def __post_init__(self) -> None:
        if not self.label:
            self.label = f"community_{self.community_id}"


@dataclass
class BridgeConcept:
    """A concept that connects two or more distinct communities."""

    concept: str
    community_id: int  # home community
    connects_communities: int  # number of distinct communities it bridges


class CommunityDetector:
    """Detects concept communities in the user's knowledge graph using Leiden.

    All graph algorithm work happens in Python (leidenalg + igraph).
    Neo4j is used only for data fetch and writing back community_id labels.
    """

    def __init__(self, graph_client: GraphClient) -> None:
        self._client = graph_client

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def detect_communities(self, user_id: int) -> list[Community]:
        """Export user KG from Neo4j, run Leiden, return community list."""
        nodes, edges = await self._fetch_graph(user_id)
        if not nodes:
            logger.info("community_detection_empty_graph", user_id=user_id)
            return []

        g, idx_to_name, mastery_map = self._build_igraph(nodes, edges)
        partition = self._run_leiden(g)

        communities: dict[int, Community] = {}
        for vertex_idx, comm_id in enumerate(partition.membership):
            concept = idx_to_name[vertex_idx]
            if comm_id not in communities:
                communities[comm_id] = Community(community_id=comm_id, concepts=[])
            communities[comm_id].concepts.append(concept)

        # Compute average mastery per community
        for comm in communities.values():
            masteries = [mastery_map.get(c, 0.0) for c in comm.concepts]
            comm.avg_mastery = sum(masteries) / len(masteries) if masteries else 0.0
            comm.label = f"community_{comm.community_id}"

        result = list(communities.values())
        logger.info(
            "communities_detected",
            user_id=user_id,
            count=len(result),
            sizes=[len(c.concepts) for c in result],
        )
        return result

    async def find_bridges(self, user_id: int) -> list[BridgeConcept]:
        """Find concepts that connect two or more distinct communities."""
        nodes, edges = await self._fetch_graph(user_id)
        if not nodes:
            return []

        g, idx_to_name, _ = self._build_igraph(nodes, edges)
        partition = self._run_leiden(g)

        # membership: vertex_idx -> community_id
        membership = partition.membership
        name_to_comm: dict[str, int] = {
            idx_to_name[i]: membership[i] for i in range(len(membership))
        }

        # For each node, find the set of communities its neighbours belong to
        bridge_map: dict[str, set[int]] = {}
        for edge in g.es:
            src_name = idx_to_name[edge.source]
            tgt_name = idx_to_name[edge.target]
            src_comm = name_to_comm[src_name]
            tgt_comm = name_to_comm[tgt_name]
            if src_comm != tgt_comm:
                bridge_map.setdefault(src_name, set()).add(src_comm)
                bridge_map[src_name].add(tgt_comm)
                bridge_map.setdefault(tgt_name, set()).add(tgt_comm)
                bridge_map[tgt_name].add(src_comm)

        bridges: list[BridgeConcept] = []
        for concept, comm_set in bridge_map.items():
            if len(comm_set) >= 2:
                bridges.append(
                    BridgeConcept(
                        concept=concept,
                        community_id=name_to_comm[concept],
                        connects_communities=len(comm_set),
                    )
                )

        logger.info("bridges_found", user_id=user_id, count=len(bridges))
        return bridges

    async def find_sparse_communities(self, user_id: int) -> list[Community]:
        """Return communities whose average mastery is below the sparse threshold."""
        communities = await self.detect_communities(user_id)
        sparse = [c for c in communities if c.avg_mastery < _SPARSE_MASTERY_THRESHOLD]
        logger.info("sparse_communities_found", user_id=user_id, count=len(sparse))
        return sparse

    async def update_community_labels(self, user_id: int, communities: list[Community]) -> None:
        """Write community_id property back to Neo4j concept nodes."""
        for community in communities:
            for concept in community.concepts:
                cypher = (
                    "MATCH (u:User {id: $user_id})-[:KNOWS]->(c:Concept {name: $concept}) "
                    "SET c.community_id = $community_id"
                )
                await self._client.execute_query(
                    cypher,
                    {
                        "user_id": user_id,
                        "concept": concept,
                        "community_id": community.community_id,
                    },
                )
        logger.info(
            "community_labels_updated",
            user_id=user_id,
            communities=len(communities),
        )

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    async def _fetch_graph(self, user_id: int) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
        """Fetch concept nodes and edges from Neo4j for a given user."""
        node_cypher = (
            "MATCH (u:User {id: $user_id})-[:KNOWS]->(c:Concept) "
            "RETURN c.name AS name, coalesce(c.mastery, 0.0) AS mastery"
        )
        edge_cypher = (
            "MATCH (u:User {id: $user_id})-[:KNOWS]->(a:Concept)-[r]->(b:Concept)"
            "<-[:KNOWS]-(u) "
            "RETURN a.name AS source, b.name AS target, "
            "coalesce(r.weight, 1.0) AS weight"
        )
        nodes = await self._client.execute_query(node_cypher, {"user_id": user_id})
        edges = await self._client.execute_query(edge_cypher, {"user_id": user_id})
        return nodes, edges

    def _build_igraph(
        self,
        nodes: list[dict[str, Any]],
        edges: list[dict[str, Any]],
    ) -> tuple[igraph.Graph, dict[int, str], dict[str, float]]:
        """Build an igraph Graph from node/edge dicts.

        Returns:
            g: undirected igraph Graph
            idx_to_name: vertex index -> concept name
            mastery_map: concept name -> mastery float
        """
        name_to_idx: dict[str, int] = {}
        idx_to_name: dict[int, str] = {}
        mastery_map: dict[str, float] = {}

        for i, node in enumerate(nodes):
            name = node["name"]
            name_to_idx[name] = i
            idx_to_name[i] = name
            mastery_map[name] = float(node.get("mastery", 0.0))

        edge_list: list[tuple[int, int]] = []
        weights: list[float] = []
        for edge in edges:
            src = edge.get("source", "")
            tgt = edge.get("target", "")
            if src in name_to_idx and tgt in name_to_idx:
                edge_list.append((name_to_idx[src], name_to_idx[tgt]))
                weights.append(float(edge.get("weight", 1.0)))

        g = igraph.Graph(
            n=len(nodes),
            edges=edge_list,
            directed=False,
        )
        if weights:
            g.es["weight"] = weights

        return g, idx_to_name, mastery_map

    def _run_leiden(self, g: igraph.Graph) -> Any:
        """Run Leiden RBConfigurationVertexPartition and return partition."""
        weights = g.es["weight"] if g.ecount() > 0 and "weight" in g.es.attributes() else None
        partition = leidenalg.find_partition(
            g,
            leidenalg.RBConfigurationVertexPartition,
            weights=weights,
            resolution_parameter=_LEIDEN_RESOLUTION,
            seed=_LEIDEN_SEED,
        )
        return partition
