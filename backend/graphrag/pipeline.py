"""Sync ingested source data into Neo4j for GraphRAG retrieval and topology build."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from backend.config import AppConfig
from backend.ingestion.ingestion_cli import SOURCE_SPECS
from backend.sanctions.matcher import normalize_name, parse_aliases

from .neo4j_store import Neo4jStore
from .topology import build_multi_tier_topology

SEC_COMPANIES_CYPHER = """
UNWIND $rows AS row
MERGE (c:Company {tenant_id: $tenant_id, company_id: row.company_id})
SET c.name = row.company_name,
    c.ticker = row.ticker,
    c.cik = row.cik
"""

SEC_FILINGS_CYPHER = """
UNWIND $rows AS row
MATCH (c:Company {tenant_id: $tenant_id, company_id: row.company_id})
MERGE (f:Filing {tenant_id: $tenant_id, filing_id: row.filing_id})
SET f.filing_date = row.filing_date,
    f.document_url = row.filing_document_url
MERGE (c)-[:FILED]->(f)
"""

SEC_SECTIONS_CYPHER = """
UNWIND $rows AS row
MATCH (f:Filing {tenant_id: $tenant_id, filing_id: row.filing_id})
MERGE (s:Section {tenant_id: $tenant_id, section_id: row.section_id})
SET s.item_code = row.item_code,
    s.title = row.title,
    s.text = row.text
MERGE (f)-[:HAS_SECTION]->(s)
"""

SUPPLIERS_CYPHER = """
UNWIND $rows AS row
MERGE (s:Supplier {tenant_id: $tenant_id, supplier_id: row.supplier_id})
SET s.name = row.name,
    s.normalized_name = row.normalized_name
"""

SEC_DEPENDS_ON_CYPHER = """
UNWIND $rows AS row
MATCH (c:Company {tenant_id: $tenant_id, company_id: row.company_id})
MATCH (s:Supplier {tenant_id: $tenant_id, supplier_id: row.supplier_id})
MERGE (c)-[r:DEPENDS_ON]->(s)
SET r.source = row.source
"""

SEC_MENTIONS_SUPPLIER_CYPHER = """
UNWIND $rows AS row
MATCH (s:Section {tenant_id: $tenant_id, section_id: row.section_id})
MATCH (sup:Supplier {tenant_id: $tenant_id, supplier_id: row.supplier_id})
MERGE (s)-[:MENTIONS_SUPPLIER]->(sup)
"""

SANCTIONS_ENTITIES_CYPHER = """
UNWIND $rows AS row
MERGE (e:SanctionEntity {tenant_id: $tenant_id, sanction_entity_id: row.sanction_entity_id})
SET e.primary_name = row.primary_name,
    e.normalized_name = row.normalized_name,
    e.source_list = row.source_list,
    e.sanctions_type = row.sanctions_type,
    e.date_published = row.date_published,
    e.address_text = row.address_text
"""

SANCTIONS_ALIASES_CYPHER = """
UNWIND $rows AS row
MATCH (e:SanctionEntity {tenant_id: $tenant_id, sanction_entity_id: row.sanction_entity_id})
MERGE (a:EntityAlias {tenant_id: $tenant_id, alias_id: row.alias_id})
SET a.alias = row.alias,
    a.normalized_alias = row.normalized_alias
MERGE (a)-[:ALIAS_OF]->(e)
"""

TRADE_COUNTRIES_CYPHER = """
UNWIND $rows AS row
MERGE (r:Country {tenant_id: $tenant_id, country_id: row.reporter_id})
SET r.name = row.reporter
MERGE (p:Country {tenant_id: $tenant_id, country_id: row.partner_id})
SET p.name = row.partner
"""

TRADE_COMMODITIES_CYPHER = """
UNWIND $rows AS row
MERGE (c:Commodity {tenant_id: $tenant_id, commodity_id: row.commodity_id})
SET c.commodity_code = row.commodity_code,
    c.description = row.commodity_desc
"""

TRADE_FLOWS_CYPHER = """
UNWIND $rows AS row
MATCH (r:Country {tenant_id: $tenant_id, country_id: row.reporter_id})
MATCH (p:Country {tenant_id: $tenant_id, country_id: row.partner_id})
MATCH (c:Commodity {tenant_id: $tenant_id, commodity_id: row.commodity_id})
MERGE (t:TradeFlow {tenant_id: $tenant_id, trade_flow_id: row.trade_flow_id})
SET t.year = row.year,
    t.flow_desc = row.flow_desc,
    t.primary_value = row.primary_value,
    t.qty = row.qty,
    t.net_wgt = row.net_wgt
MERGE (r)-[:REPORTED_FLOW]->(t)
MERGE (t)-[:TO_PARTNER]->(p)
MERGE (t)-[:FOR_COMMODITY]->(c)
"""

TRADE_DATASOURCE_CYPHER = """
UNWIND $rows AS row
MERGE (d:DataSource {tenant_id: $tenant_id, source_name: row.source_name})
SET d.latest_trade_year = row.latest_trade_year,
    d.data_lag_years = row.data_lag_years,
    d.freshness_note = row.freshness_note
"""

HAZARD_COUNTRY_CYPHER = """
UNWIND $rows AS row
MERGE (c:Country {tenant_id: $tenant_id, country_id: row.country_id})
SET c.name = row.country_name
"""

HAZARD_REGIONS_CYPHER = """
UNWIND $rows AS row
MATCH (c:Country {tenant_id: $tenant_id, country_id: row.country_id})
MERGE (g:GeoRegion {tenant_id: $tenant_id, region_id: row.region_id})
SET g.state = row.state,
    g.county = row.county
MERGE (g)-[:IN_COUNTRY]->(c)
"""

HAZARD_EVENTS_CYPHER = """
UNWIND $rows AS row
MATCH (g:GeoRegion {tenant_id: $tenant_id, region_id: row.region_id})
MERGE (h:HazardEvent {tenant_id: $tenant_id, hazard_event_id: row.hazard_event_id})
SET h.event_type = row.event_type,
    h.event_year = row.event_year,
    h.property_damage_usd = row.property_damage_usd,
    h.crop_damage_usd = row.crop_damage_usd,
    h.begin_lat = row.begin_lat,
    h.begin_lon = row.begin_lon,
    h.end_lat = row.end_lat,
    h.end_lon = row.end_lon
MERGE (h)-[:AFFECTS_REGION]->(g)
"""

REGULATORY_ACTIONS_CYPHER = """
UNWIND $rows AS row
MATCH (s:Supplier {tenant_id: $tenant_id, supplier_id: row.supplier_id})
MERGE (a:RegulatoryAction {tenant_id: $tenant_id, action_id: row.action_id})
SET a.action_type = 'FDA_WARNING_LETTER',
    a.issue_date = row.issue_date,
    a.subject = row.subject,
    a.issuing_office = row.issuing_office,
    a.severity = row.severity
MERGE (a)-[:TARGETS]->(s)
"""

_SUPPLIER_PATTERNS = [
    re.compile(r"\b([A-Z][A-Za-z0-9&.,'() -]{2,80}(?:Inc\.?|Corp\.?|Corporation|Ltd\.?|Limited|LLC|PLC|Company|Co\.|Technologies|Technology|Precision Industry|Semiconductor Manufacturing Company))\b"),
    re.compile(r"\b(TSMC|SK Hynix|Micron Technology|Samsung Electronics|Hon Hai Precision Industry|Wistron Corporation|Fabrinet)\b"),
]


def _load_sections(sections_json_path: Path) -> list[dict[str, Any]]:
    if not sections_json_path.exists():
        return []
    loaded = json.loads(sections_json_path.read_text(encoding="utf-8"))
    return loaded if isinstance(loaded, list) else []


def _load_local_graph_rows(settings: AppConfig, tenant_id: str) -> tuple[dict[str, list[dict[str, Any]]], dict[str, str]]:
    rows_by_source: dict[str, list[dict[str, Any]]] = {}
    source_paths: dict[str, str] = {}
    for source_name in ("ofac_sdn", "comtrade", "noaa", "fda"):
        spec = SOURCE_SPECS[source_name]
        source_path = spec.resolve_path(settings.project_root)
        if not source_path.exists():
            raise RuntimeError(
                f"Graph RAG local-source fallback could not find `{source_name}` at `{source_path}`."
            )
        source_paths[source_name] = str(source_path)
        rows_by_source[source_name] = list(spec.iterator_factory(tenant_id, source_path))
    return rows_by_source, source_paths


def _load_graph_source_rows(
    settings: AppConfig,
    tenant_id: str,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]], str, dict[str, str]]:
    local_rows, source_paths = _load_local_graph_rows(settings, tenant_id)
    return (
        local_rows["ofac_sdn"],
        local_rows["comtrade"],
        local_rows["noaa"],
        local_rows["fda"],
        "local_files",
        source_paths,
    )


def _supplier_mentions(text: str) -> list[str]:
    found: list[str] = []
    for pattern in _SUPPLIER_PATTERNS:
        for match in pattern.finditer(text or ""):
            supplier = str(match.group(1)).strip().strip(",.;")
            if supplier and supplier not in found:
                found.append(supplier)
    return found[:20]


def _severity_from_subject(subject: str) -> str:
    lowered = (subject or "").lower()
    if any(token in lowered for token in ("sterility", "contamination", "critical")):
        return "high"
    if any(token in lowered for token in ("capa", "quality", "deviation")):
        return "medium"
    return "low"


def build_graph_sync_batches(
    *,
    tenant_id: str,
    sections: list[dict[str, Any]],
    sanctions_rows: list[dict[str, Any]],
    trade_rows: list[dict[str, Any]],
    hazard_rows: list[dict[str, Any]],
    regulatory_rows: list[dict[str, Any]],
) -> dict[str, Any]:
    companies: list[dict[str, Any]] = []
    filings: list[dict[str, Any]] = []
    section_rows: list[dict[str, Any]] = []
    suppliers: dict[str, dict[str, Any]] = {}
    depends_on: list[dict[str, Any]] = []
    mentions_supplier: list[dict[str, Any]] = []

    for row in sections:
        ticker = str(row.get("ticker", "") or "").strip().upper()
        company_name = str(row.get("company_name", "") or "").strip()
        filing_date = str(row.get("filing_date", "") or "").strip()
        if not ticker or not company_name:
            continue
        company_id = f"company:{ticker}"
        filing_id = f"filing:{ticker}:{filing_date or 'latest'}"
        companies.append(
            {
                "company_id": company_id,
                "company_name": company_name,
                "ticker": ticker,
                "cik": str(row.get("cik", "") or ""),
            }
        )
        filings.append(
            {
                "company_id": company_id,
                "filing_id": filing_id,
                "filing_date": filing_date,
                "filing_document_url": str(row.get("filing_document_url", "") or ""),
            }
        )
        raw_sections = row.get("sections", {}) if isinstance(row.get("sections"), dict) else {}
        for item_code, text in raw_sections.items():
            text_value = str(text or "").strip()
            if not text_value:
                continue
            section_id = f"{filing_id}:{item_code}"
            section_rows.append(
                {
                    "filing_id": filing_id,
                    "section_id": section_id,
                    "item_code": item_code,
                    "title": item_code.upper(),
                    "text": text_value,
                }
            )
            for supplier_name in _supplier_mentions(text_value):
                supplier_id = f"supplier:{normalize_name(supplier_name).replace(' ', '_')}"
                suppliers.setdefault(
                    supplier_id,
                    {
                        "supplier_id": supplier_id,
                        "name": supplier_name,
                        "normalized_name": normalize_name(supplier_name),
                    },
                )
                depends_on.append({"company_id": company_id, "supplier_id": supplier_id, "source": item_code})
                mentions_supplier.append({"section_id": section_id, "supplier_id": supplier_id})

    sanctions_entities: list[dict[str, Any]] = []
    sanctions_aliases: list[dict[str, Any]] = []
    for row in sanctions_rows:
        entity_id = f"sanction:{row['source_entity_id']}"
        sanctions_entities.append(
            {
                "sanction_entity_id": entity_id,
                "primary_name": row.get("primary_name", ""),
                "normalized_name": normalize_name(str(row.get("primary_name", "") or "")),
                "source_list": row.get("source_file_name", ""),
                "sanctions_type": row.get("sanctions_type", ""),
                "date_published": row.get("date_published", ""),
                "address_text": row.get("address_text", ""),
            }
        )
        for alias in parse_aliases(str(row.get("aliases", "") or "")):
            alias_norm = normalize_name(alias)
            if not alias_norm:
                continue
            sanctions_aliases.append(
                {
                    "sanction_entity_id": entity_id,
                    "alias_id": f"{entity_id}:alias:{alias_norm.replace(' ', '_')}",
                    "alias": alias,
                    "normalized_alias": alias_norm,
                }
            )

    trade_country_rows: list[dict[str, Any]] = []
    trade_commodity_rows: list[dict[str, Any]] = []
    trade_flow_rows: list[dict[str, Any]] = []
    latest_trade_year = 0
    for row in trade_rows:
        reporter = str(row.get("reporter_desc", "") or "").strip() or "Unknown Reporter"
        partner = str(row.get("partner_desc", "") or "").strip() or "Unknown Partner"
        commodity_code = str(row.get("cmd_code", "") or "").strip() or "UNKNOWN"
        commodity_desc = str(row.get("cmd_desc", "") or "").strip() or "Unknown Commodity"
        year = int(row.get("ref_year") or 0)
        latest_trade_year = max(latest_trade_year, year)
        reporter_id = f"country:{normalize_name(reporter).replace(' ', '_')}"
        partner_id = f"country:{normalize_name(partner).replace(' ', '_')}"
        commodity_id = f"commodity:{normalize_name(commodity_code or commodity_desc).replace(' ', '_')}"
        trade_country_rows.append(
            {
                "reporter_id": reporter_id,
                "reporter": reporter,
                "partner_id": partner_id,
                "partner": partner,
            }
        )
        trade_commodity_rows.append(
            {
                "commodity_id": commodity_id,
                "commodity_code": commodity_code,
                "commodity_desc": commodity_desc,
            }
        )
        trade_flow_rows.append(
            {
                "trade_flow_id": f"trade:{year}:{reporter_id}:{partner_id}:{commodity_id}",
                "reporter_id": reporter_id,
                "partner_id": partner_id,
                "commodity_id": commodity_id,
                "year": year,
                "flow_desc": str(row.get("flow_desc", "") or ""),
                "primary_value": float(row.get("primary_value") or 0.0),
                "qty": float(row.get("qty") or 0.0),
                "net_wgt": float(row.get("net_wgt") or 0.0),
            }
        )

    hazard_country_rows = [{"country_id": "country:united_states", "country_name": "United States"}]
    hazard_region_rows: list[dict[str, Any]] = []
    hazard_event_rows: list[dict[str, Any]] = []
    for row in hazard_rows:
        state = str(row.get("state", "") or "").strip() or "UNKNOWN"
        county = str(row.get("cz_name", "") or "").strip() or "UNKNOWN"
        region_id = f"region:{normalize_name(state)}:{normalize_name(county)}"
        hazard_region_rows.append(
            {
                "region_id": region_id,
                "state": state,
                "county": county,
                "country_id": "country:united_states",
            }
        )
        hazard_event_rows.append(
            {
                "hazard_event_id": f"hazard:{row.get('event_id')}",
                "region_id": region_id,
                "event_type": row.get("event_type", ""),
                "event_year": int(row.get("year") or 0),
                "property_damage_usd": float(row.get("damage_property_usd") or 0.0),
                "crop_damage_usd": float(row.get("damage_crops_usd") or 0.0),
                "begin_lat": row.get("begin_lat"),
                "begin_lon": row.get("begin_lon"),
                "end_lat": row.get("end_lat"),
                "end_lon": row.get("end_lon"),
            }
        )

    regulatory_action_rows: list[dict[str, Any]] = []
    for row in regulatory_rows:
        supplier_name = str(row.get("company_name", "") or "").strip()
        if not supplier_name:
            continue
        supplier_id = f"supplier:{normalize_name(supplier_name).replace(' ', '_')}"
        suppliers.setdefault(
            supplier_id,
            {
                "supplier_id": supplier_id,
                "name": supplier_name,
                "normalized_name": normalize_name(supplier_name),
            },
        )
        regulatory_action_rows.append(
            {
                "action_id": f"regulatory:{row.get('source_record_hash')}",
                "supplier_id": supplier_id,
                "issue_date": row.get("letter_issue_date", ""),
                "subject": row.get("subject", ""),
                "issuing_office": row.get("issuing_office", ""),
                "severity": _severity_from_subject(str(row.get("subject", "") or "")),
            }
        )

    return {
        "sec_filings": {
            "companies": companies,
            "filings": filings,
            "sections": section_rows,
            "suppliers": list(suppliers.values()),
            "depends_on": depends_on,
            "mentions_supplier": mentions_supplier,
        },
        "sanctions": {
            "entities": sanctions_entities,
            "aliases": sanctions_aliases,
        },
        "trade": {
            "countries": trade_country_rows,
            "commodities": trade_commodity_rows,
            "flows": trade_flow_rows,
            "datasource": [
                {
                    "source_name": "UN_COMTRADE",
                    "latest_trade_year": latest_trade_year,
                    "data_lag_years": max(0, 2026 - latest_trade_year) if latest_trade_year else None,
                    "freshness_note": "Comtrade data updates periodically and may lag the current calendar year.",
                }
            ] if latest_trade_year else [],
        },
        "hazards": {
            "countries": hazard_country_rows,
            "regions": hazard_region_rows,
            "events": hazard_event_rows,
        },
        "regulatory": {
            "actions": regulatory_action_rows,
        },
    }


def sync_graph_state(
    settings: AppConfig,
    *,
    sections_json_path: Path | None = None,
) -> dict[str, Any]:
    tenant_id = settings.graph_tenant_id
    sections_path = sections_json_path or (settings.project_root / "data/ingestion/sec/extracted_10k_sections.json")
    sections = _load_sections(sections_path)
    (
        sanctions_rows,
        trade_rows,
        hazard_rows,
        regulatory_rows,
        source_mode,
        source_paths,
    ) = _load_graph_source_rows(settings, tenant_id)

    batches = build_graph_sync_batches(
        tenant_id=tenant_id,
        sections=sections,
        sanctions_rows=sanctions_rows,
        trade_rows=trade_rows,
        hazard_rows=hazard_rows,
        regulatory_rows=regulatory_rows,
    )

    store = Neo4jStore(settings)
    try:
        sec = batches["sec_filings"]
        store.write_rows(SEC_COMPANIES_CYPHER, sec["companies"], tenant_id=tenant_id)
        store.write_rows(SEC_FILINGS_CYPHER, sec["filings"], tenant_id=tenant_id)
        store.write_rows(SEC_SECTIONS_CYPHER, sec["sections"], tenant_id=tenant_id)
        store.write_rows(SUPPLIERS_CYPHER, sec["suppliers"], tenant_id=tenant_id)
        store.write_rows(SEC_DEPENDS_ON_CYPHER, sec["depends_on"], tenant_id=tenant_id)
        store.write_rows(SEC_MENTIONS_SUPPLIER_CYPHER, sec["mentions_supplier"], tenant_id=tenant_id)

        sanctions = batches["sanctions"]
        store.write_rows(SANCTIONS_ENTITIES_CYPHER, sanctions["entities"], tenant_id=tenant_id)
        store.write_rows(SANCTIONS_ALIASES_CYPHER, sanctions["aliases"], tenant_id=tenant_id)

        trade = batches["trade"]
        store.write_rows(TRADE_COUNTRIES_CYPHER, trade["countries"], tenant_id=tenant_id)
        store.write_rows(TRADE_COMMODITIES_CYPHER, trade["commodities"], tenant_id=tenant_id)
        store.write_rows(TRADE_FLOWS_CYPHER, trade["flows"], tenant_id=tenant_id)
        if trade["datasource"]:
            store.write_rows(TRADE_DATASOURCE_CYPHER, trade["datasource"], tenant_id=tenant_id)

        hazards = batches["hazards"]
        store.write_rows(HAZARD_COUNTRY_CYPHER, hazards["countries"], tenant_id=tenant_id)
        store.write_rows(HAZARD_REGIONS_CYPHER, hazards["regions"], tenant_id=tenant_id)
        store.write_rows(HAZARD_EVENTS_CYPHER, hazards["events"], tenant_id=tenant_id)

        store.write_rows(REGULATORY_ACTIONS_CYPHER, batches["regulatory"]["actions"], tenant_id=tenant_id)
    finally:
        store.close()

    topology = build_multi_tier_topology(settings)
    return {
        "tenant_id": tenant_id,
        "sections_json_path": str(sections_path),
        "source_mode": source_mode,
        "source_paths": source_paths,
        "batches": {
            "sec_filings": {key: len(value) for key, value in batches["sec_filings"].items()},
            "sanctions": {key: len(value) for key, value in batches["sanctions"].items()},
            "trade": {key: len(value) for key, value in batches["trade"].items()},
            "hazards": {key: len(value) for key, value in batches["hazards"].items()},
            "regulatory": {key: len(value) for key, value in batches["regulatory"].items()},
        },
        "topology": topology,
    }


