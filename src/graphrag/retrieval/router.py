"""Rule-based router for Graph RAG retrieval strategies."""

from __future__ import annotations

from ..utils import tokenize_terms


ROUTE_KEYWORDS = {
    "sanctions": {
        "ofac",
        "sdn",
        "sanction",
        "entity list",
        "bis",
        "huawei",
        "restricted",
        "blocked",
    },
    "trade": {
        "comtrade",
        "import",
        "export",
        "commodity",
        "hs",
        "gallium",
        "germanium",
        "cobalt",
        "lithium",
        "rare earth",
    },
    "hazard": {
        "noaa",
        "hurricane",
        "storm",
        "flood",
        "wildfire",
        "earthquake",
        "hazard",
        "gulf coast",
    },
    "regulatory": {
        "fda",
        "quality",
        "warning letter",
        "import alert",
        "adulterated",
        "cder",
        "compliance",
    },
    "financial": {
        "10-k",
        "risk factor",
        "item 1a",
        "item 7",
        "md&a",
        "single source supplier",
        "going concern",
        "supplier dependence",
    },
    "cascade": {
        "cascade",
        "downstream",
        "tier",
        "affected products",
        "single point of failure",
        "exposure",
    },
}


def route_question(question: str) -> list[str]:
    """Choose one or more retrieval routes."""
    q = (question or "").lower()
    routes: list[str] = []
    for route, keywords in ROUTE_KEYWORDS.items():
        for keyword in keywords:
            if keyword in q:
                routes.append(route)
                break
    if not routes:
        # Broad default blend for enterprise questions.
        routes = ["financial", "sanctions", "trade", "hazard", "regulatory"]
    # De-dup, preserve order.
    deduped: list[str] = []
    for route in routes:
        if route not in deduped:
            deduped.append(route)
    return deduped


def query_terms(question: str) -> list[str]:
    """Extract route-agnostic lexical terms."""
    return tokenize_terms(question, min_len=3)
