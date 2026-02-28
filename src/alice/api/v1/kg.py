"""Knowledge Graph API — interactive visualization and editing endpoints."""

from __future__ import annotations

from typing import Annotated, Any

import structlog
from fastapi import APIRouter, HTTPException, Query

from alice.config import settings
from alice.graph.client import (
    GraphClient,
    get_shared_graph_client,
    make_edge_id,
    parse_edge_id,
)
from alice.graph.schema import RelType
from alice.schemas.kg import (
    KGCommunityOut,
    KGEdgeCreateIn,
    KGEdgeOut,
    KGEdgeOut2,
    KGGapAnalysis,
    KGGapSuggestion,
    KGGraphOut,
    KGNodeOut,
    KGNodeUpdateIn,
)

logger = structlog.get_logger(__name__)

router = APIRouter(prefix="/kg", tags=["knowledge-graph"])

# Valid relationship types for edge creation
_VALID_REL_TYPES = {
    RelType.PREREQUISITE_OF,
    RelType.EXTENDS,
    RelType.APPLIES_TO,
    RelType.CONTRASTS,
    RelType.KNOWS,
    RelType.DISCUSSES,
}


def _neo4j_auth() -> tuple[str, str]:
    """Parse NEO4J_AUTH setting into (user, password) tuple."""
    user, password = settings.NEO4J_AUTH.split("/", 1)
    return (user, password)


async def _get_client() -> GraphClient:
    """Return the shared (pooled) Neo4j client, falling back to per-request if needed."""
    try:
        return await get_shared_graph_client(settings.NEO4J_URI, _neo4j_auth())
    except Exception:
        # Fallback: create a per-request client (won't be closed automatically here,
        # but this path only triggers if the singleton failed, which is rare).
        client = GraphClient(settings.NEO4J_URI, _neo4j_auth())
        await client.connect()
        return client


@router.get("/graph", response_model=KGGraphOut)
async def get_kg_graph(
    user_id: Annotated[int, Query(ge=1, description="User ID")] = 1,
    depth: Annotated[int, Query(ge=1, le=5, description="Traversal depth from center")] = 3,
    center: Annotated[str | None, Query(description="Center concept name (optional)")] = None,
    max_nodes: Annotated[int, Query(ge=10, le=1000, description="Maximum nodes to return")] = 200,
) -> Any:
    """Return the user's knowledge graph in React Flow compatible format.

    If `center` is provided, returns a subgraph centered on that concept.
    Otherwise returns the full user KG up to `max_nodes`.
    """
    try:
        client = await _get_client()
        if center:
            return await _get_centered_subgraph(client, user_id, center, depth, max_nodes)
        return await _get_full_user_graph(client, user_id, max_nodes)
    except Exception as exc:
        logger.error("kg_graph_error", error=str(exc), user_id=user_id)
        raise HTTPException(status_code=500, detail="Failed to load knowledge graph")


async def _get_full_user_graph(
    client: GraphClient, user_id: int, max_nodes: int
) -> KGGraphOut:
    """Fetch the full user knowledge graph from Neo4j."""
    # Get all concepts the user KNOWS with mastery, community info, and total count
    nodes_cypher = (
        "MATCH (u:User {id: $user_id})-[r:KNOWS]->(c) "
        "WITH c, r ORDER BY r.mastery DESC LIMIT $limit "
        "WITH COLLECT({name: c.name, labels: labels(c), mastery: r.mastery, "
        "  aliases: c.aliases, community_id: c.community_id}) AS nodes_data "
        "OPTIONAL MATCH (u2:User {id: $user_id})-[:KNOWS]->(total_c) "
        "WITH nodes_data, count(total_c) AS total_count "
        "UNWIND nodes_data AS nd "
        "RETURN nd.name AS name, nd.labels AS labels, nd.mastery AS mastery, "
        "nd.aliases AS aliases, nd.community_id AS community_id, total_count"
    )
    node_rows = await client.execute_query(
        nodes_cypher, {"user_id": user_id, "limit": max_nodes}
    )

    if not node_rows:
        return KGGraphOut(nodes=[], edges=[], total_nodes=0, total_edges=0)

    total_nodes = node_rows[0].get("total_count", len(node_rows)) if node_rows else 0
    node_names = {r["name"] for r in node_rows}

    # Get edges between known concepts
    edges_cypher = (
        "MATCH (u:User {id: $user_id})-[:KNOWS]->(c1)-[r]->(c2)<-[:KNOWS]-(u) "
        "WHERE type(r) <> 'KNOWS' AND type(r) <> 'DISCUSSES' "
        "RETURN DISTINCT c1.name AS source, c2.name AS target, type(r) AS relation"
    )
    edge_rows = await client.execute_query(edges_cypher, {"user_id": user_id})

    nodes = [
        KGNodeOut(
            id=row["name"],
            name=row["name"],
            label=_primary_label(row.get("labels", [])),
            mastery=row.get("mastery") or 0.0,
            community_id=row.get("community_id"),
            aliases=row.get("aliases") or [],
        )
        for row in node_rows
    ]

    edges = [
        KGEdgeOut(
            id=make_edge_id(row["source"], row["relation"], row["target"]),
            source=row["source"],
            target=row["target"],
            label=row["relation"],
        )
        for row in edge_rows
        if row["source"] in node_names and row["target"] in node_names
    ]

    return KGGraphOut(
        nodes=nodes,
        edges=edges,
        total_nodes=total_nodes,
        total_edges=len(edges),
    )


async def _get_centered_subgraph(
    client: GraphClient,
    user_id: int,
    center: str,
    depth: int,
    max_nodes: int,
) -> KGGraphOut:
    """Fetch a subgraph centered on a specific concept."""
    # BFS from center concept up to `depth` hops
    nodes_cypher = (
        "MATCH (start:Concept {name: $center}) "
        f"MATCH path = (start)-[*1..{depth}]-(neighbor) "
        "WHERE neighbor:Concept OR neighbor:Method OR neighbor:Tool OR neighbor:Theory "
        "WITH DISTINCT neighbor "
        "LIMIT $limit "
        "OPTIONAL MATCH (u:User {id: $user_id})-[r:KNOWS]->(neighbor) "
        "RETURN neighbor.name AS name, labels(neighbor) AS labels, "
        "r.mastery AS mastery, neighbor.aliases AS aliases, "
        "neighbor.community_id AS community_id"
    )
    node_rows = await client.execute_query(
        nodes_cypher,
        {"center": center, "user_id": user_id, "limit": max_nodes - 1},
    )

    # Always include the center node
    center_cypher = (
        "MATCH (c:Concept {name: $center}) "
        "OPTIONAL MATCH (u:User {id: $user_id})-[r:KNOWS]->(c) "
        "RETURN c.name AS name, labels(c) AS labels, r.mastery AS mastery, "
        "c.aliases AS aliases, c.community_id AS community_id"
    )
    center_rows = await client.execute_query(
        center_cypher, {"center": center, "user_id": user_id}
    )

    all_rows = center_rows + [r for r in node_rows if r["name"] != center]
    node_names = {r["name"] for r in all_rows}

    # Get edges between these nodes
    edges_cypher = (
        "MATCH (c1)-[r]->(c2) "
        "WHERE c1.name IN $names AND c2.name IN $names "
        "AND type(r) <> 'KNOWS' AND type(r) <> 'DISCUSSES' "
        "RETURN DISTINCT c1.name AS source, c2.name AS target, type(r) AS relation"
    )
    edge_rows = await client.execute_query(edges_cypher, {"names": list(node_names)})

    nodes = [
        KGNodeOut(
            id=row["name"],
            name=row["name"],
            label=_primary_label(row.get("labels", [])),
            mastery=row.get("mastery") or 0.0,
            community_id=row.get("community_id"),
            aliases=row.get("aliases") or [],
        )
        for row in all_rows
    ]

    edges = [
        KGEdgeOut(
            id=make_edge_id(row["source"], row["relation"], row["target"]),
            source=row["source"],
            target=row["target"],
            label=row["relation"],
        )
        for row in edge_rows
    ]

    return KGGraphOut(
        nodes=nodes,
        edges=edges,
        total_nodes=len(nodes),
        total_edges=len(edges),
    )


@router.get("/communities", response_model=list[KGCommunityOut])
async def get_kg_communities(
    user_id: Annotated[int, Query(ge=1, description="User ID")] = 1,
) -> Any:
    """Return community cluster list with node counts."""
    try:
        from alice.services.community_detection import CommunityDetector

        client = await _get_client()
        detector = CommunityDetector(client)
        communities = await detector.detect_communities(user_id)
        return [
            KGCommunityOut(
                community_id=c.community_id,
                label=c.label,
                concept_count=len(c.concepts),
                avg_mastery=c.avg_mastery,
                concepts=c.concepts,
            )
            for c in communities
        ]
    except Exception as exc:
        logger.error("kg_communities_error", error=str(exc), user_id=user_id)
        raise HTTPException(status_code=500, detail="Failed to load communities")


@router.get("/gaps", response_model=KGGapAnalysis)
async def get_knowledge_gaps(
    user_id: Annotated[int, Query(ge=1, description="User ID")] = 1,
    limit: Annotated[int, Query(ge=1, le=50)] = 10,
) -> Any:
    """Analyze knowledge gaps — low-mastery concepts adjacent to mastered ones.

    Returns concepts the user should learn next based on their graph neighborhood.
    """
    try:
        client = await _get_client()
        # Find concepts at the boundary: connected to mastered concepts (>0.7)
        # but user has low mastery (<0.3) or doesn't know them
        cypher = (
            "MATCH (u:User {id: $user_id})-[rk:KNOWS]->(mastered) "
            "WHERE rk.mastery > 0.7 "
            "MATCH (mastered)-[rel]-(candidate) "
            "WHERE (candidate:Concept OR candidate:Method OR candidate:Tool OR candidate:Theory) "
            "AND type(rel) <> 'KNOWS' AND type(rel) <> 'DISCUSSES' "
            "OPTIONAL MATCH (u)-[rc:KNOWS]->(candidate) "
            "WITH candidate, COALESCE(rc.mastery, 0.0) AS candidate_mastery, "
            "COLLECT(DISTINCT mastered.name) AS adjacent_mastered "
            "WHERE candidate_mastery < 0.3 "
            "RETURN candidate.name AS concept, candidate_mastery AS mastery, "
            "adjacent_mastered "
            "ORDER BY candidate_mastery ASC, SIZE(adjacent_mastered) DESC "
            "LIMIT $limit"
        )
        rows = await client.execute_query(cypher, {"user_id": user_id, "limit": limit})

        gaps = [
            KGGapSuggestion(
                concept=row["concept"],
                mastery=row["mastery"],
                adjacent_mastered=row["adjacent_mastered"][:5],
                reason=f"与已掌握概念 {', '.join(row['adjacent_mastered'][:3])} 相邻",
            )
            for row in rows
        ]

        return KGGapAnalysis(gaps=gaps, total_gaps=len(gaps))
    except Exception as exc:
        logger.error("kg_gaps_error", error=str(exc), user_id=user_id)
        raise HTTPException(status_code=500, detail="Failed to analyze knowledge gaps")


@router.patch("/node/{node_id}")
async def update_kg_node(
    node_id: str,
    body: KGNodeUpdateIn,
    user_id: Annotated[int, Query(ge=1, description="User ID")] = 1,
) -> dict[str, Any]:
    """Update a KG node's mastery or name."""
    try:
        client = await _get_client()
        updates: list[str] = []
        params: dict[str, Any] = {"user_id": user_id, "node_id": node_id}

        if body.mastery is not None:
            updates.append("r.mastery = $mastery")
            updates.append("r.last_reviewed = datetime()")
            params["mastery"] = body.mastery

        if body.name is not None and body.name != node_id:
            rename_cypher = (
                "MATCH (c:Concept {name: $node_id}) "
                "SET c.name = $new_name "
                "RETURN c.name AS name"
            )
            params["new_name"] = body.name
            await client.execute_query(rename_cypher, params)

        if body.mastery is not None:
            mastery_cypher = (
                "MATCH (u:User {id: $user_id})-[r:KNOWS]->(c:Concept {name: $target_name}) "
                f"SET {', '.join(updates)} "
                "RETURN c.name AS name, r.mastery AS mastery"
            )
            params["target_name"] = body.name if body.name else node_id
            rows = await client.execute_query(mastery_cypher, params)
            if not rows:
                raise HTTPException(status_code=404, detail=f"Concept '{node_id}' not found or user has no KNOWS relationship")
            return {"name": rows[0]["name"], "mastery": rows[0]["mastery"], "updated": True}

        return {"name": body.name or node_id, "updated": True}
    except HTTPException:
        raise
    except Exception as exc:
        logger.error("kg_node_update_error", error=str(exc), node_id=node_id)
        raise HTTPException(status_code=500, detail="Failed to update node")


@router.post("/edge", response_model=KGEdgeOut2)
async def create_kg_edge(
    body: KGEdgeCreateIn,
    user_id: Annotated[int, Query(ge=1, description="User ID")] = 1,
) -> Any:
    """Create a relationship between two concept nodes."""
    if body.relation not in _VALID_REL_TYPES:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid relation type '{body.relation}'. Valid: {sorted(_VALID_REL_TYPES)}"
        )

    try:
        client = await _get_client()
        cypher = (
            "MATCH (a:Concept {name: $source}) "
            "MATCH (b:Concept {name: $target}) "
            f"MERGE (a)-[r:{body.relation}]->(b) "
            "RETURN a.name AS source, b.name AS target, type(r) AS relation"
        )
        rows = await client.execute_query(
            cypher, {"source": body.source, "target": body.target}
        )
        if not rows:
            raise HTTPException(
                status_code=404,
                detail=f"One or both concepts not found: '{body.source}', '{body.target}'"
            )
        row = rows[0]
        return KGEdgeOut2(
            id=make_edge_id(row["source"], row["relation"], row["target"]),
            source=row["source"],
            target=row["target"],
            relation=row["relation"],
            created=True,
        )
    except HTTPException:
        raise
    except Exception as exc:
        logger.error("kg_edge_create_error", error=str(exc))
        raise HTTPException(status_code=500, detail="Failed to create edge")


@router.delete("/edge/{edge_id}")
async def delete_kg_edge(
    edge_id: str,
    user_id: Annotated[int, Query(ge=1, description="User ID")] = 1,
) -> dict[str, Any]:
    """Delete a relationship between two concept nodes.

    edge_id format: 'source::RELATION_TYPE::target'
    """
    try:
        source, relation, target = parse_edge_id(edge_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid edge_id format. Expected 'source::RELATION::target'")

    # Validate relation type against whitelist to prevent Cypher injection
    if relation not in _VALID_REL_TYPES:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid relation type '{relation}'. Valid: {sorted(_VALID_REL_TYPES)}"
        )

    try:
        client = await _get_client()
        cypher = (
            f"MATCH (a:Concept {{name: $source}})-[r:{relation}]->(b:Concept {{name: $target}}) "
            "DELETE r "
            "RETURN a.name AS source, b.name AS target"
        )
        rows = await client.execute_query(
            cypher, {"source": source, "target": target}
        )
        if not rows:
            raise HTTPException(status_code=404, detail=f"Edge not found: {edge_id}")
        return {"deleted": True, "edge_id": edge_id}
    except HTTPException:
        raise
    except Exception as exc:
        logger.error("kg_edge_delete_error", error=str(exc), edge_id=edge_id)
        raise HTTPException(status_code=500, detail="Failed to delete edge")


def _primary_label(labels: list[str]) -> str:
    """Extract the primary concept label from a list of Neo4j labels."""
    priority = ["Method", "Tool", "Theory", "Concept"]
    for p in priority:
        if p in labels:
            return p
    return labels[0] if labels else "Concept"
