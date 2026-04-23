"""Build canonical multi-tier supply chain topology on top of existing graph data."""

from __future__ import annotations

from typing import Any

from config import AppConfig

from .neo4j_store import Neo4jStore


CONSTRAINTS = [
    "CREATE CONSTRAINT company_unique IF NOT EXISTS FOR (n:Company) REQUIRE (n.tenant_id, n.company_id) IS UNIQUE",
    "CREATE CONSTRAINT supplier_unique IF NOT EXISTS FOR (n:Supplier) REQUIRE (n.tenant_id, n.supplier_id) IS UNIQUE",
    "CREATE CONSTRAINT component_unique IF NOT EXISTS FOR (n:Component) REQUIRE (n.tenant_id, n.component_id) IS UNIQUE",
    "CREATE CONSTRAINT material_unique IF NOT EXISTS FOR (n:RawMaterial) REQUIRE (n.tenant_id, n.material_id) IS UNIQUE",
    "CREATE CONSTRAINT hazard_zone_unique IF NOT EXISTS FOR (n:HazardZone) REQUIRE (n.tenant_id, n.hazard_zone_id) IS UNIQUE",
    "CREATE CONSTRAINT sanctions_status_unique IF NOT EXISTS FOR (n:SanctionsStatus) REQUIRE (n.tenant_id, n.status_id) IS UNIQUE",
    "CREATE INDEX supplier_norm_idx IF NOT EXISTS FOR (n:Supplier) ON (n.normalized_name)",
    "CREATE INDEX section_item_idx IF NOT EXISTS FOR (n:Section) ON (n.item_code)",
    "CREATE INDEX section_text_idx IF NOT EXISTS FOR (n:Section) ON (n.text)",
]


SYNC_TIER1_CYPHER = """
MATCH (c:Company {tenant_id: $tenant_id})-[:DEPENDS_ON]->(s:Supplier {tenant_id: $tenant_id})
MERGE (c)-[r:HAS_TIER1_SUPPLIER]->(s)
SET s.tier_level = coalesce(s.tier_level, 1),
    r.source = coalesce(r.source, 'DEPENDS_ON')
RETURN count(r) AS total
"""

SYNC_TIER2_FROM_SECTIONS_CYPHER = """
MATCH (c:Company {tenant_id: $tenant_id})-[:HAS_TIER1_SUPPLIER]->(s1:Supplier {tenant_id: $tenant_id})
MATCH (c)-[:FILED]->(:Filing {tenant_id: $tenant_id})-[:HAS_SECTION]->(sec:Section {tenant_id: $tenant_id})-[:MENTIONS_SUPPLIER]->(s1)
MATCH (sec)-[:MENTIONS_SUPPLIER]->(s2:Supplier {tenant_id: $tenant_id})
WHERE s1 <> s2
MERGE (s1)-[r:HAS_TIER2_SUPPLIER]->(s2)
SET s2.tier_level = coalesce(s2.tier_level, 2),
    r.evidence = coalesce(r.evidence, 'section_co_mention')
RETURN count(r) AS total
"""

CREATE_COMPONENTS_CYPHER = """
MATCH (cmd:Commodity {tenant_id: $tenant_id})
WITH cmd WHERE cmd.commodity_code IS NOT NULL OR cmd.description IS NOT NULL
WITH cmd,
     coalesce(cmd.commodity_code, toLower(replace(replace(cmd.description, ' ', '_'), '/', '_'))) AS key
MERGE (comp:Component {tenant_id: $tenant_id, component_id: 'component:' + key})
SET comp.name = coalesce(cmd.description, cmd.commodity_code),
    comp.commodity_code = cmd.commodity_code
MERGE (raw:RawMaterial {tenant_id: $tenant_id, material_id: 'material:' + key})
SET raw.name = coalesce(cmd.description, cmd.commodity_code),
    raw.commodity_code = cmd.commodity_code
MERGE (comp)-[:USES_MATERIAL]->(raw)
RETURN count(comp) AS total
"""

LINK_MATERIAL_COUNTRY_CYPHER = """
MATCH (t:TradeFlow {tenant_id: $tenant_id})-[:FOR_COMMODITY]->(cmd:Commodity {tenant_id: $tenant_id})
MATCH (t)-[:TO_PARTNER]->(country:Country {tenant_id: $tenant_id})
MATCH (raw:RawMaterial {tenant_id: $tenant_id, commodity_code: cmd.commodity_code})
MERGE (raw)-[:SOURCED_FROM]->(country)
RETURN count(*) AS total
"""

CREATE_HAZARD_ZONES_CYPHER = """
MATCH (g:GeoRegion {tenant_id: $tenant_id})<-[:AFFECTS_REGION]-(h:HazardEvent {tenant_id: $tenant_id})
WITH g,
     count(h) AS event_count,
     sum(coalesce(h.property_damage_usd,0)+coalesce(h.crop_damage_usd,0)) AS total_damage,
     avg(coalesce(h.begin_lat, h.end_lat)) AS avg_lat,
     avg(coalesce(h.begin_lon, h.end_lon)) AS avg_lon
MERGE (hz:HazardZone {tenant_id: $tenant_id, hazard_zone_id: 'hz:' + coalesce(g.region_id, g.state + ':' + g.county)})
SET hz.state = g.state,
    hz.county = g.county,
    hz.event_count = event_count,
    hz.total_damage_usd = total_damage,
    hz.avg_lat = avg_lat,
    hz.avg_lon = avg_lon
MERGE (g)-[:MAPS_TO_HAZARD_ZONE]->(hz)
WITH g, hz
MATCH (g)-[:IN_COUNTRY]->(c:Country {tenant_id: $tenant_id})
MERGE (c)-[:IN_HAZARD_ZONE]->(hz)
RETURN count(hz) AS total
"""

SANCTIONS_STATUS_PRIMARY_CYPHER = """
MATCH (s:Supplier {tenant_id: $tenant_id})
MATCH (e:SanctionEntity {tenant_id: $tenant_id})
WHERE s.normalized_name IS NOT NULL
  AND s.normalized_name <> ''
  AND s.normalized_name = e.normalized_name
MERGE (ss:SanctionsStatus {tenant_id: $tenant_id, status_id: 'ss:' + s.supplier_id + ':exact_primary:' + e.sanction_entity_id})
SET ss.status = 'MATCHED',
    ss.match_type = 'exact_primary',
    ss.matched_entity = e.primary_name,
    ss.source_list = e.source_list,
    ss.updated_at = datetime()
MERGE (s)-[:SANCTIONS_STATUS]->(ss)
RETURN count(ss) AS total
"""

SANCTIONS_STATUS_ALIAS_CYPHER = """
MATCH (s:Supplier {tenant_id: $tenant_id})
MATCH (a:EntityAlias {tenant_id: $tenant_id})-[:ALIAS_OF]->(e:SanctionEntity {tenant_id: $tenant_id})
WHERE s.normalized_name IS NOT NULL
  AND s.normalized_name <> ''
  AND s.normalized_name = a.normalized_alias
MERGE (ss:SanctionsStatus {tenant_id: $tenant_id, status_id: 'ss:' + s.supplier_id + ':exact_alias:' + e.sanction_entity_id})
SET ss.status = 'MATCHED',
    ss.match_type = 'exact_alias',
    ss.matched_entity = e.primary_name,
    ss.alias_used = a.alias,
    ss.source_list = e.source_list,
    ss.updated_at = datetime()
MERGE (s)-[:SANCTIONS_STATUS]->(ss)
RETURN count(ss) AS total
"""

SANCTIONS_STATUS_CLEAR_CYPHER = """
MATCH (s:Supplier {tenant_id: $tenant_id})
WHERE NOT (s)-[:SANCTIONS_STATUS]->(:SanctionsStatus {tenant_id: $tenant_id})
MERGE (ss:SanctionsStatus {tenant_id: $tenant_id, status_id: 'ss:' + s.supplier_id + ':clear'})
SET ss.status = 'CLEAR',
    ss.match_type = 'none',
    ss.updated_at = datetime()
MERGE (s)-[:SANCTIONS_STATUS]->(ss)
RETURN count(ss) AS total
"""

FETCH_COMPONENTS_CYPHER = """
MATCH (c:Component {tenant_id: $tenant_id})
RETURN c.component_id AS component_id, toLower(coalesce(c.name, '')) AS component_name
"""

FETCH_SUPPLIER_SECTION_TEXT_CYPHER = """
MATCH (sec:Section {tenant_id: $tenant_id})-[:MENTIONS_SUPPLIER]->(s:Supplier {tenant_id: $tenant_id})
RETURN s.supplier_id AS supplier_id, collect(toLower(coalesce(sec.text,'')))[0..8] AS texts
"""

LINK_SUPPLIER_COMPONENT_CYPHER = """
UNWIND $rows AS row
MATCH (s:Supplier {tenant_id: $tenant_id, supplier_id: row.supplier_id})
MATCH (c:Component {tenant_id: $tenant_id, component_id: row.component_id})
MERGE (s)-[:SUPPLIES_COMPONENT]->(c)
RETURN count(*) AS total
"""

PROPAGATE_TIER2_COMPONENT_CYPHER = """
MATCH (s1:Supplier {tenant_id: $tenant_id})-[:HAS_TIER2_SUPPLIER]->(s2:Supplier {tenant_id: $tenant_id})
MATCH (s1)-[:SUPPLIES_COMPONENT]->(c:Component {tenant_id: $tenant_id})
MERGE (s2)-[:SUPPLIES_COMPONENT]->(c)
RETURN count(*) AS total
"""


def _keywords(name: str) -> list[str]:
    tokens = [tok.strip() for tok in name.split() if tok and len(tok.strip()) >= 5]
    blocked = {"other", "parts", "articles", "goods", "value", "products", "total"}
    out: list[str] = []
    for token in tokens:
        token = "".join(ch for ch in token if ch.isalnum())
        token = token.lower()
        if len(token) < 5 or token in blocked:
            continue
        if token not in out:
            out.append(token)
        if len(out) >= 6:
            break
    return out


def build_multi_tier_topology(settings: AppConfig) -> dict[str, Any]:
    """Build canonical multi-tier graph relationships from existing ingested data."""
    store = Neo4jStore(settings)
    tenant_id = settings.graph_tenant_id
    summary: dict[str, Any] = {"tenant_id": tenant_id}
    try:
        for ddl in CONSTRAINTS:
            store.execute_write(ddl)

        summary["tier1_links"] = store.execute_write_return(SYNC_TIER1_CYPHER, {"tenant_id": tenant_id})[0]["total"]
        summary["tier2_links"] = store.execute_write_return(
            SYNC_TIER2_FROM_SECTIONS_CYPHER, {"tenant_id": tenant_id}
        )[0]["total"]
        summary["components_created"] = store.execute_write_return(
            CREATE_COMPONENTS_CYPHER, {"tenant_id": tenant_id}
        )[0]["total"]
        summary["material_country_links"] = store.execute_write_return(
            LINK_MATERIAL_COUNTRY_CYPHER, {"tenant_id": tenant_id}
        )[0]["total"]
        summary["hazard_zones"] = store.execute_write_return(
            CREATE_HAZARD_ZONES_CYPHER, {"tenant_id": tenant_id}
        )[0]["total"]

        summary["sanctions_exact_primary"] = store.execute_write_return(
            SANCTIONS_STATUS_PRIMARY_CYPHER, {"tenant_id": tenant_id}
        )[0]["total"]
        summary["sanctions_exact_alias"] = store.execute_write_return(
            SANCTIONS_STATUS_ALIAS_CYPHER, {"tenant_id": tenant_id}
        )[0]["total"]
        summary["sanctions_clear"] = store.execute_write_return(
            SANCTIONS_STATUS_CLEAR_CYPHER, {"tenant_id": tenant_id}
        )[0]["total"]

        components = store.execute_read(FETCH_COMPONENTS_CYPHER, {"tenant_id": tenant_id})
        component_keywords = [(row["component_id"], _keywords(row.get("component_name", ""))) for row in components]

        supplier_sections = store.execute_read(FETCH_SUPPLIER_SECTION_TEXT_CYPHER, {"tenant_id": tenant_id})
        link_rows: list[dict[str, str]] = []
        for supplier_row in supplier_sections:
            supplier_id = supplier_row.get("supplier_id")
            texts = supplier_row.get("texts") or []
            text_blob = "\n".join(t for t in texts if isinstance(t, str))[:120000]
            if not supplier_id or not text_blob:
                continue
            for component_id, kws in component_keywords:
                if not kws:
                    continue
                if any(kw in text_blob for kw in kws):
                    link_rows.append({"supplier_id": supplier_id, "component_id": component_id})
            if len(link_rows) >= 10000:
                break

        if link_rows:
            summary["supplier_component_links"] = store.write_rows(
                LINK_SUPPLIER_COMPONENT_CYPHER,
                link_rows,
                tenant_id=tenant_id,
                batch_size=500,
            )
        else:
            summary["supplier_component_links"] = 0

        summary["tier2_component_links"] = store.execute_write_return(
            PROPAGATE_TIER2_COMPONENT_CYPHER, {"tenant_id": tenant_id}
        )[0]["total"]
        return summary
    finally:
        store.close()

