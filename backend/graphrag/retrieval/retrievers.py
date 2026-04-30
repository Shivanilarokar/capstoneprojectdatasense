"""Cypher-backed retrievers aligned to SupplyChainNexus route requirements."""

from __future__ import annotations

import re
from typing import Any

from ..neo4j_store import Neo4jStore


FINANCIAL_HEALTH_CYPHER = """
MATCH (c:Company {tenant_id: $tenant_id})-[:FILED]->(f:Filing {tenant_id: $tenant_id})-[:HAS_SECTION]->(s:Section {tenant_id: $tenant_id})
WHERE s.item_code IN ['item1a', 'item7', 'item7a', 'item8']
  AND ($has_terms = false OR any(term IN $terms
      WHERE toLower(coalesce(c.name, '')) CONTAINS term
         OR toLower(coalesce(c.ticker, '')) CONTAINS term
         OR toLower(coalesce(s.text, '')) CONTAINS term))
RETURN c.name AS company,
       c.ticker AS ticker,
       f.filing_date AS filing_date,
       s.item_code AS item_code,
       left(s.text, 1400) AS section_snippet,
       s.text AS section_text
ORDER BY CASE
           WHEN any(term IN $terms
                    WHERE toLower(coalesce(c.name, '')) CONTAINS term
                       OR toLower(coalesce(c.ticker, '')) CONTAINS term)
           THEN 0 ELSE 1
         END,
         f.filing_date DESC
LIMIT $limit
"""

SANCTIONS_LIST_CYPHER = """
MATCH (e:SanctionEntity {tenant_id: $tenant_id})
OPTIONAL MATCH (a:EntityAlias {tenant_id: $tenant_id})-[:ALIAS_OF]->(e)
WITH e, collect(DISTINCT a.alias)[0..6] AS aliases
WHERE $has_terms = false OR any(term IN $terms
      WHERE toLower(e.primary_name) CONTAINS term
         OR any(alias IN aliases WHERE toLower(alias) CONTAINS term))
RETURN e.primary_name AS name,
       e.source_list AS source_list,
       e.sanctions_type AS sanctions_type,
       e.date_published AS date_published,
       aliases
ORDER BY e.date_published DESC
LIMIT $limit
"""

SANCTIONS_EXACT_PRIMARY_CYPHER = """
MATCH (s:Supplier {tenant_id: $tenant_id})
MATCH (e:SanctionEntity {tenant_id: $tenant_id})
WHERE s.normalized_name IS NOT NULL
  AND s.normalized_name <> ''
  AND s.normalized_name = e.normalized_name
  AND ($has_terms = false OR any(term IN $terms
      WHERE toLower(coalesce(s.name, '')) CONTAINS term
         OR toLower(coalesce(e.primary_name, '')) CONTAINS term))
RETURN s.name AS supplier,
       e.primary_name AS sanctioned_entity,
       'exact_primary' AS match_type,
       1.0 AS score,
       e.source_list AS source_list
ORDER BY supplier, sanctioned_entity
LIMIT $limit
"""

SANCTIONS_EXACT_ALIAS_CYPHER = """
MATCH (s:Supplier {tenant_id: $tenant_id})
MATCH (a:EntityAlias {tenant_id: $tenant_id})-[:ALIAS_OF]->(e:SanctionEntity {tenant_id: $tenant_id})
WHERE s.normalized_name IS NOT NULL
  AND s.normalized_name <> ''
  AND s.normalized_name = a.normalized_alias
  AND ($has_terms = false OR any(term IN $terms
      WHERE toLower(coalesce(s.name, '')) CONTAINS term
         OR toLower(coalesce(e.primary_name, '')) CONTAINS term
         OR toLower(coalesce(a.alias, '')) CONTAINS term))
RETURN s.name AS supplier,
       e.primary_name AS sanctioned_entity,
       a.alias AS alias_used,
       'exact_alias' AS match_type,
       0.99 AS score,
       e.source_list AS source_list
ORDER BY supplier, sanctioned_entity
LIMIT $limit
"""

TRADE_AGG_CYPHER = """
MATCH (r:Country {tenant_id: $tenant_id})-[:REPORTED_FLOW]->(t:TradeFlow {tenant_id: $tenant_id})-[:TO_PARTNER]->(p:Country {tenant_id: $tenant_id})
OPTIONAL MATCH (t)-[:FOR_COMMODITY]->(c:Commodity {tenant_id: $tenant_id})
WHERE ($has_terms = false OR any(term IN $terms
      WHERE toLower(coalesce(c.description, '')) CONTAINS term
         OR toLower(coalesce(c.commodity_code, '')) CONTAINS term
         OR toLower(coalesce(r.name, '')) CONTAINS term
         OR toLower(coalesce(p.name, '')) CONTAINS term))
WITH t.year AS year,
     coalesce(c.commodity_code, 'UNKNOWN') AS commodity_code,
     coalesce(c.description, 'UNKNOWN') AS commodity_desc,
     r.name AS reporter,
     p.name AS partner,
     coalesce(t.flow_desc, t.flow_code) AS flow,
     sum(coalesce(t.primary_value, 0)) AS total_trade_value,
     sum(coalesce(t.qty, 0)) AS total_qty
RETURN year,
       commodity_code,
       commodity_desc,
       reporter,
       partner,
       flow,
       total_trade_value,
       total_qty
ORDER BY year DESC, total_trade_value DESC
LIMIT $limit
"""

TRADE_CONCENTRATION_CYPHER = """
MATCH (r:Country {tenant_id: $tenant_id})-[:REPORTED_FLOW]->(t:TradeFlow {tenant_id: $tenant_id})-[:FOR_COMMODITY]->(c:Commodity {tenant_id: $tenant_id})
WHERE ($has_terms = false OR any(term IN $terms
      WHERE toLower(coalesce(c.description, '')) CONTAINS term
         OR toLower(coalesce(c.commodity_code, '')) CONTAINS term
         OR toLower(coalesce(r.name, '')) CONTAINS term))
WITH t.year AS year,
     coalesce(c.commodity_code, 'UNKNOWN') AS commodity_code,
     coalesce(c.description, 'UNKNOWN') AS commodity_desc,
     r.name AS country,
     sum(coalesce(t.primary_value, 0)) AS country_value
WITH year, commodity_code, commodity_desc,
     collect({country: country, value: country_value}) AS by_country,
     sum(country_value) AS total_value
RETURN year, commodity_code, commodity_desc, total_value, by_country[0..5] AS top_country_values
ORDER BY year DESC, total_value DESC
LIMIT $limit
"""

TRADE_FRESHNESS_CYPHER = """
MATCH (ds:DataSource {tenant_id: $tenant_id, source_name: 'UN_COMTRADE'})
RETURN ds.latest_trade_year AS latest_trade_year,
       ds.data_lag_years AS data_lag_years,
       ds.freshness_note AS freshness_note
LIMIT 1
"""

HAZARD_GEO_TEMPORAL_CYPHER = """
MATCH (h:HazardEvent {tenant_id: $tenant_id})-[:AFFECTS_REGION]->(g:GeoRegion {tenant_id: $tenant_id})
WHERE ($has_terms = false OR any(term IN $terms
      WHERE toLower(coalesce(h.event_type, '')) CONTAINS term
         OR toLower(coalesce(g.state, '')) CONTAINS term
         OR toLower(coalesce(g.county, '')) CONTAINS term))
WITH g.state AS state,
     g.county AS county,
     h.event_type AS event_type,
     min(h.event_year) AS first_year,
     max(h.event_year) AS last_year,
     count(*) AS event_count,
     sum(coalesce(h.property_damage_usd,0)+coalesce(h.crop_damage_usd,0)) AS total_damage_usd,
     avg(coalesce(h.begin_lat, h.end_lat)) AS avg_lat,
     avg(coalesce(h.begin_lon, h.end_lon)) AS avg_lon
RETURN state,
       county,
       event_type,
       first_year,
       last_year,
       event_count,
       total_damage_usd,
       avg_lat,
       avg_lon
ORDER BY event_count DESC, total_damage_usd DESC
LIMIT $limit
"""

HAZARD_ZONE_CYPHER = """
MATCH (country:Country {tenant_id: $tenant_id})-[:IN_HAZARD_ZONE]->(hz:HazardZone {tenant_id: $tenant_id})
WHERE $has_terms = false OR any(term IN $terms
      WHERE toLower(coalesce(country.name, '')) CONTAINS term
         OR toLower(coalesce(hz.state, '')) CONTAINS term
         OR toLower(coalesce(hz.county, '')) CONTAINS term)
RETURN country.name AS country,
       hz.state AS state,
       hz.county AS county,
       hz.event_count AS event_count,
       hz.total_damage_usd AS total_damage_usd
ORDER BY hz.event_count DESC, hz.total_damage_usd DESC
LIMIT $limit
"""

REGULATORY_QUALITY_CYPHER = """
MATCH (a:RegulatoryAction {tenant_id: $tenant_id})-[:TARGETS]->(s:Supplier {tenant_id: $tenant_id})
WHERE ($has_terms = false OR any(term IN $terms
      WHERE toLower(coalesce(a.subject, '')) CONTAINS term
         OR toLower(coalesce(s.name, '')) CONTAINS term
         OR toLower(coalesce(a.issuing_office, '')) CONTAINS term))
OPTIONAL MATCH (s)-[:SANCTIONS_STATUS]->(ss:SanctionsStatus {tenant_id: $tenant_id})
WITH a, s, collect(DISTINCT ss.match_type)[0..4] AS sanctions_statuses
RETURN a.action_type AS action_type,
       a.issue_date AS issue_date,
       s.name AS company,
       a.subject AS subject,
       a.issuing_office AS issuing_office,
       a.severity AS severity,
       sanctions_statuses
ORDER BY a.issue_date DESC
LIMIT $limit
"""

CASCADE_CANONICAL_CYPHER = """
MATCH (c:Company {tenant_id: $tenant_id})-[:HAS_TIER1_SUPPLIER]->(t1:Supplier {tenant_id: $tenant_id})
MATCH (t1)-[:HAS_TIER2_SUPPLIER]->(t2:Supplier {tenant_id: $tenant_id})
OPTIONAL MATCH (t2)-[r_sc]->(comp:Component {tenant_id: $tenant_id})
OPTIONAL MATCH (comp)-[r_um]->(raw:RawMaterial {tenant_id: $tenant_id})
OPTIONAL MATCH (raw)-[r_so]->(country:Country {tenant_id: $tenant_id})
OPTIONAL MATCH (country)-[r_ih]->(hz:HazardZone {tenant_id: $tenant_id})
OPTIONAL MATCH (t2)-[r_ss]->(ss:SanctionsStatus {tenant_id: $tenant_id})
WHERE (r_sc IS NULL OR type(r_sc) = 'SUPPLIES_COMPONENT')
  AND (r_um IS NULL OR type(r_um) = 'USES_MATERIAL')
  AND (r_so IS NULL OR type(r_so) = 'SOURCED_FROM')
  AND (r_ih IS NULL OR type(r_ih) = 'IN_HAZARD_ZONE')
  AND (r_ss IS NULL OR type(r_ss) = 'SANCTIONS_STATUS')
  AND ($has_terms = false OR any(term IN $terms
      WHERE toLower(coalesce(c.name, '')) CONTAINS term
         OR toLower(coalesce(t1.name, '')) CONTAINS term
         OR toLower(coalesce(t2.name, '')) CONTAINS term
         OR toLower(coalesce(comp.name, '')) CONTAINS term
         OR toLower(coalesce(raw.name, '')) CONTAINS term
         OR toLower(coalesce(country.name, '')) CONTAINS term
         OR toLower(coalesce(hz.state, '')) CONTAINS term))
RETURN c.name AS company,
       c.ticker AS ticker,
       t1.name AS tier1_supplier,
       t2.name AS tier2_supplier,
       comp.name AS component,
       raw.name AS raw_material,
       country.name AS source_country,
       (hz.state + ':' + hz.county) AS hazard_zone,
       ss.status AS sanctions_status,
       ss.match_type AS sanctions_match_type
ORDER BY company, tier1_supplier, tier2_supplier
LIMIT $limit
"""

CASCADE_FALLBACK_CYPHER = """
MATCH (c:Company {tenant_id: $tenant_id})-[:DEPENDS_ON]->(s:Supplier {tenant_id: $tenant_id})
WHERE ($has_terms = false OR any(term IN $terms
      WHERE toLower(coalesce(c.name, '')) CONTAINS term
         OR toLower(coalesce(s.name, '')) CONTAINS term))
RETURN c.name AS company,
       c.ticker AS ticker,
       s.name AS supplier
ORDER BY company, supplier
LIMIT $limit
"""


TABLE_LINE_RE = re.compile(r"\d")
MULTI_NUM_RE = re.compile(r"(?:\d[\d,]*(?:\.\d+)?)")


def _extract_table_lines(text: str, max_lines: int = 12) -> list[str]:
    """Extract table-like lines from SEC narrative text."""
    lines: list[str] = []
    for raw in (text or "").splitlines():
        line = raw.strip()
        if len(line) < 6:
            continue
        if not TABLE_LINE_RE.search(line):
            continue
        number_hits = MULTI_NUM_RE.findall(line)
        if len(number_hits) < 2:
            continue
        lines.append(line)
        if len(lines) >= max_lines:
            break
    return lines


def _params(tenant_id: str, terms: list[str], limit: int) -> dict[str, Any]:
    return {"tenant_id": tenant_id, "terms": terms, "has_terms": bool(terms), "limit": limit}


def _read_with_term_fallback(
    store: Neo4jStore,
    cypher: str,
    tenant_id: str,
    terms: list[str],
    limit: int,
) -> list[dict[str, Any]]:
    rows = store.execute_read(cypher, _params(tenant_id, terms, limit))
    if rows or not terms:
        return rows
    return store.execute_read(cypher, _params(tenant_id, [], limit))


def retrieve_route(
    store: Neo4jStore,
    route: str,
    tenant_id: str,
    terms: list[str],
    limit: int,
) -> dict[str, Any]:
    """Run route-specific query and return structured evidence."""
    if route == "financial":
        rows = _read_with_term_fallback(store, FINANCIAL_HEALTH_CYPHER, tenant_id, terms, limit)
        table_evidence: list[dict[str, Any]] = []
        for row in rows:
            table_lines = _extract_table_lines(row.get("section_text", ""))
            if table_lines:
                table_evidence.append(
                    {
                        "company": row.get("company"),
                        "ticker": row.get("ticker"),
                        "filing_date": row.get("filing_date"),
                        "item_code": row.get("item_code"),
                        "table_lines": table_lines,
                    }
                )
            row.pop("section_text", None)
        return {
            "route": route,
            "financial_health": rows,
            "financial_tables": table_evidence,
        }

    if route == "sanctions":
        sanctions_list = _read_with_term_fallback(store, SANCTIONS_LIST_CYPHER, tenant_id, terms, limit)
        exact_primary = _read_with_term_fallback(store, SANCTIONS_EXACT_PRIMARY_CYPHER, tenant_id, terms, limit)
        exact_alias = _read_with_term_fallback(store, SANCTIONS_EXACT_ALIAS_CYPHER, tenant_id, terms, limit)
        exact_matches = exact_primary + exact_alias
        return {
            "route": route,
            "sanctions_list": sanctions_list,
            "exact_entity_matches": exact_matches,
        }

    if route == "trade":
        aggregated_flows = _read_with_term_fallback(store, TRADE_AGG_CYPHER, tenant_id, terms, limit)
        concentration = _read_with_term_fallback(store, TRADE_CONCENTRATION_CYPHER, tenant_id, terms, limit)
        freshness = store.execute_read(TRADE_FRESHNESS_CYPHER, {"tenant_id": tenant_id})
        return {
            "route": route,
            "commodity_trade_flows": aggregated_flows,
            "commodity_concentration": concentration,
            "freshness": freshness[0] if freshness else None,
        }

    if route == "hazard":
        geotemporal = _read_with_term_fallback(store, HAZARD_GEO_TEMPORAL_CYPHER, tenant_id, terms, limit)
        hazard_zones = _read_with_term_fallback(store, HAZARD_ZONE_CYPHER, tenant_id, terms, limit)
        return {
            "route": route,
            "natural_hazard_geotemporal": geotemporal,
            "hazard_zones": hazard_zones,
        }

    if route == "regulatory":
        quality_rows = _read_with_term_fallback(store, REGULATORY_QUALITY_CYPHER, tenant_id, terms, limit)
        return {
            "route": route,
            "quality_regulatory_actions": quality_rows,
        }

    if route == "cascade":
        canonical = _read_with_term_fallback(store, CASCADE_CANONICAL_CYPHER, tenant_id, terms, limit)
        if canonical:
            return {"route": route, "multi_tier_paths": canonical, "topology_mode": "canonical"}
        fallback = _read_with_term_fallback(store, CASCADE_FALLBACK_CYPHER, tenant_id, terms, limit)
        return {"route": route, "multi_tier_paths": fallback, "topology_mode": "fallback"}

    return {"route": route, "error": f"Unknown route: {route}"}


