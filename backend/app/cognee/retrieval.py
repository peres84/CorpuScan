from __future__ import annotations

import logging

from app.cognee.client import CogneeClient

logger = logging.getLogger(__name__)


async def search_context(client: CogneeClient, query: str) -> str:
    """Semantic search against Cognee's knowledge memory.

    Returns formatted context text for the investigation agent.
    Falls back to empty string if Cognee is unavailable.
    """
    if not client.is_available():
        return ""

    try:
        import cognee

        results = await cognee.recall(
            query_text=query,
            query_type=cognee.SearchType.GRAPH_COMPLETION,
        )

        return _format_recall_results(results, query)
    except Exception:
        logger.debug("Cognee search_context failed for query: %s", query)
        return ""


async def find_related_entities(
    client: CogneeClient, entity_name: str
) -> list[dict[str, str]]:
    """Find entities related to the given entity via Cognee's knowledge graph.

    Returns a list of dicts with 'name', 'type', and 'relationship' keys.
    Falls back to empty list if Cognee is unavailable.
    """
    if not client.is_available():
        return []

    try:
        import cognee

        results = await cognee.recall(
            query_text=f"What entities are connected to {entity_name}? List relationships.",
            query_type=cognee.SearchType.GRAPH_COMPLETION,
        )

        return _parse_related_entities(results)
    except Exception:
        logger.debug("Cognee find_related_entities failed for: %s", entity_name)
        return []


async def get_relationship_graph(
    client: CogneeClient, entity_name: str
) -> dict[str, object]:
    """Get the relationship subgraph centered on the given entity.

    Returns a dict with 'entities' and 'relationships' lists.
    Falls back to empty graph if Cognee is unavailable.
    """
    if not client.is_available():
        return {"entities": [], "relationships": []}

    try:
        import cognee

        results = await cognee.recall(
            query_text=f"Show the relationship graph for {entity_name} including all connections.",
            query_type=cognee.SearchType.GRAPH_COMPLETION,
        )

        return _parse_relationship_graph(results)
    except Exception:
        logger.debug("Cognee get_relationship_graph failed for: %s", entity_name)
        return {"entities": [], "relationships": []}


def _format_recall_results(results: object, query: str) -> str:
    """Format Cognee recall results into a readable string for the LLM."""
    if not results:
        return ""

    if isinstance(results, str):
        return f"Cognee knowledge context for '{query}':\n{results}"

    if isinstance(results, list):
        parts: list[str] = [f"Cognee knowledge context for '{query}':"]
        for item in results[:10]:
            if isinstance(item, dict):
                content = item.get("content") or item.get("text") or str(item)
                parts.append(f"- {content[:300]}")
            elif isinstance(item, str):
                parts.append(f"- {item[:300]}")
        return "\n".join(parts)

    return str(results)[:1000]


def _parse_related_entities(results: object) -> list[dict[str, str]]:
    """Parse Cognee results into a list of related entity dicts."""
    entities: list[dict[str, str]] = []

    if not results:
        return entities

    if isinstance(results, list):
        for item in results:
            if isinstance(item, dict):
                name = str(item.get("name") or item.get("entity") or "")
                if name:
                    entities.append(
                        {
                            "name": name,
                            "type": str(item.get("type", "unknown")),
                            "relationship": str(item.get("relationship", "related")),
                        }
                    )

    return entities


def _parse_relationship_graph(results: object) -> dict[str, object]:
    """Parse Cognee results into a graph structure."""
    graph: dict[str, object] = {"entities": [], "relationships": []}

    if not results:
        return graph

    if isinstance(results, dict):
        graph["entities"] = results.get("entities", results.get("nodes", []))
        graph["relationships"] = results.get("relationships", results.get("edges", []))

    return graph


def register_cognee_mcp_tools(client: CogneeClient) -> None:
    """Register Cognee retrieval tools in the MCP registry."""
    from app.mcp.registry import register_tool

    async def _mcp_search(query: str) -> dict[str, object]:
        result = await search_context(client, query)
        return {"query": query, "context": result}

    async def _mcp_related(entity_name: str) -> dict[str, object]:
        entities = await find_related_entities(client, entity_name)
        return {"entity": entity_name, "related": entities}

    async def _mcp_graph(entity_name: str) -> dict[str, object]:
        graph = await get_relationship_graph(client, entity_name)
        return {"entity": entity_name, "graph": graph}

    register_tool(
        name="cognee.search",
        description="Search Cognee knowledge memory for context related to a query.",
        handler=_mcp_search,  # type: ignore[arg-type]
        parameters={"query": "Natural language search query"},
    )
    register_tool(
        name="cognee.related_entities",
        description="Find entities related to a given entity in the Cognee knowledge graph.",
        handler=_mcp_related,  # type: ignore[arg-type]
        parameters={"entity_name": "Name of the entity to find relationships for"},
    )
    register_tool(
        name="cognee.relationship_graph",
        description="Get the relationship subgraph centered on an entity from Cognee.",
        handler=_mcp_graph,  # type: ignore[arg-type]
        parameters={"entity_name": "Name of the entity to get the graph for"},
    )

    logger.info(
        "Cognee MCP tools registered: cognee.search, cognee.related_entities, cognee.relationship_graph"
    )
