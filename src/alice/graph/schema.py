"""Neo4j graph schema constants — node labels, relationship types, Cypher DDL."""

from __future__ import annotations


# ── Node Labels ────────────────────────────────────────────────────────────────
class NodeLabel:
    CONCEPT = "Concept"
    METHOD = "Method"
    TOOL = "Tool"
    THEORY = "Theory"
    USER = "User"
    CONTENT = "Content"


# ── Relationship Types ─────────────────────────────────────────────────────────
class RelType:
    KNOWS = "KNOWS"
    PREREQUISITE_OF = "PREREQUISITE_OF"
    EXTENDS = "EXTENDS"
    APPLIES_TO = "APPLIES_TO"
    DISCUSSES = "DISCUSSES"
    CONTRASTS = "CONTRASTS"


# ── Cypher DDL ─────────────────────────────────────────────────────────────────
# Constraints (uniqueness)
CONSTRAINT_CONCEPT_NAME = (
    "CREATE CONSTRAINT concept_name_unique IF NOT EXISTS FOR (c:Concept) REQUIRE c.name IS UNIQUE"
)
CONSTRAINT_CONTENT_ID = (
    "CREATE CONSTRAINT content_id_unique IF NOT EXISTS FOR (c:Content) REQUIRE c.id IS UNIQUE"
)
CONSTRAINT_USER_ID = (
    "CREATE CONSTRAINT user_id_unique IF NOT EXISTS FOR (u:User) REQUIRE u.id IS UNIQUE"
)

# Indexes (lookup performance)
INDEX_CONCEPT_NAME = "CREATE INDEX concept_name_idx IF NOT EXISTS FOR (c:Concept) ON (c.name)"
INDEX_CONTENT_SOURCE = (
    "CREATE INDEX content_source_idx IF NOT EXISTS FOR (c:Content) ON (c.source_url)"
)

SCHEMA_STATEMENTS: list[str] = [
    CONSTRAINT_CONCEPT_NAME,
    CONSTRAINT_CONTENT_ID,
    CONSTRAINT_USER_ID,
    INDEX_CONCEPT_NAME,
    INDEX_CONTENT_SOURCE,
]
