from __future__ import annotations


ROUTE_GUIDANCE: dict[str, list[str]] = {
    "weather": [
        "Use source_noaa_storm_events for storm, hazard, damage, fatalities, and event-type questions.",
        "Prefer damage_property_usd or damage_crops_usd for monetary impact.",
        "When ranking states or event types, aggregate first and order descending by the aggregate alias.",
    ],
    "trade": [
        "Use source_comtrade_flows for importer/exporter, commodity, and value questions.",
        "Use flow_code = 'X' for exports and flow_code = 'M' for imports when the user asks specifically.",
        "Prefer primary_value for trade value rankings unless the question explicitly asks for CIF or FOB.",
    ],
    "fda": [
        "Use source_fda_warning_letters for company, issuing_office, severity, and posted_date questions.",
        "Group by company_name or issuing_office when counting letters.",
        "Use severity and risk_category directly when the user asks for high-risk or severe letters.",
    ],
    "sanctions": [
        "Use source_ofac_sdn_entities for sanctions program, entity type, nationality, citizenship, and alias questions.",
        "Group by sanctions_programs or entity_type for ranking questions.",
        "Use aliases only for descriptive output or deterministic matching, not fuzzy expansion.",
    ],
    "cross_source": [
        "Use deterministic normalized-name matching only for cross-source FDA and OFAC overlap questions.",
        "Prefer company_name_normalized from FDA when populated.",
        "Compare the FDA normalized name against both OFAC primary_name and normalized aliases text.",
        "Return distinct overlaps and avoid duplicate rows caused by alias matches.",
    ],
}


ROUTE_EXAMPLES: dict[str, list[dict[str, str]]] = {
    "weather": [
        {
            "question": "Which states had the highest total property damage?",
            "sql": (
                "SELECT state, SUM(damage_property_usd) AS total_damage_usd "
                "FROM source_noaa_storm_events "
                "WHERE tenant_id = %(tenant_id)s "
                "GROUP BY state ORDER BY total_damage_usd DESC LIMIT 5"
            ),
        },
        {
            "question": "Which event types caused the most crop damage?",
            "sql": (
                "SELECT event_type, SUM(damage_crops_usd) AS total_crop_damage_usd "
                "FROM source_noaa_storm_events "
                "WHERE tenant_id = %(tenant_id)s "
                "GROUP BY event_type ORDER BY total_crop_damage_usd DESC LIMIT 5"
            ),
        },
    ],
    "trade": [
        {
            "question": "Which countries had the highest export value in 2023?",
            "sql": (
                "SELECT reporter_desc, SUM(primary_value) AS total_value "
                "FROM source_comtrade_flows "
                "WHERE tenant_id = %(tenant_id)s AND ref_year = 2023 AND flow_code = 'X' "
                "GROUP BY reporter_desc ORDER BY total_value DESC LIMIT 5"
            ),
        },
        {
            "question": "Which partners received the highest import value in 2023?",
            "sql": (
                "SELECT partner_desc, SUM(primary_value) AS total_value "
                "FROM source_comtrade_flows "
                "WHERE tenant_id = %(tenant_id)s AND ref_year = 2023 AND flow_code = 'M' "
                "GROUP BY partner_desc ORDER BY total_value DESC LIMIT 5"
            ),
        },
    ],
    "fda": [
        {
            "question": "Which companies received the most FDA warning letters?",
            "sql": (
                "SELECT company_name, COUNT(*) AS warning_count "
                "FROM source_fda_warning_letters "
                "WHERE tenant_id = %(tenant_id)s "
                "GROUP BY company_name ORDER BY warning_count DESC LIMIT 5"
            ),
        },
        {
            "question": "Which issuing offices sent the most high-severity warning letters?",
            "sql": (
                "SELECT issuing_office, COUNT(*) AS warning_count "
                "FROM source_fda_warning_letters "
                "WHERE tenant_id = %(tenant_id)s AND severity = 'high' "
                "GROUP BY issuing_office ORDER BY warning_count DESC LIMIT 5"
            ),
        },
    ],
    "sanctions": [
        {
            "question": "Which sanctions programs have the most listed entities?",
            "sql": (
                "SELECT sanctions_programs, COUNT(*) AS entity_count "
                "FROM source_ofac_sdn_entities "
                "WHERE tenant_id = %(tenant_id)s "
                "GROUP BY sanctions_programs ORDER BY entity_count DESC LIMIT 5"
            ),
        },
        {
            "question": "How many SDN entities are organizations versus individuals?",
            "sql": (
                "SELECT entity_type, COUNT(*) AS entity_count "
                "FROM source_ofac_sdn_entities "
                "WHERE tenant_id = %(tenant_id)s "
                "GROUP BY entity_type ORDER BY entity_count DESC"
            ),
        },
    ],
    "cross_source": [
        {
            "question": "Which companies appear in both FDA warning letters and the OFAC SDN list?",
            "sql": (
                "WITH fda AS ("
                "SELECT company_name, "
                "coalesce(nullif(company_name_normalized, ''), "
                "trim(regexp_replace(regexp_replace(regexp_replace(lower(coalesce(company_name, '')), '[^a-z0-9\\s]', '', 'g'), '\\m(inc|corp|corporation|ltd|limited|llc|co|company)\\M', '', 'g'), '\\s+', ' ', 'g'))) AS fda_normalized "
                "FROM source_fda_warning_letters WHERE tenant_id = %(tenant_id)s"
                "), "
                "sdn AS ("
                "SELECT primary_name, aliases, "
                "trim(regexp_replace(regexp_replace(regexp_replace(lower(coalesce(primary_name, '')), '[^a-z0-9\\s]', '', 'g'), '\\m(inc|corp|corporation|ltd|limited|llc|co|company)\\M', '', 'g'), '\\s+', ' ', 'g')) AS ofac_primary_normalized, "
                "trim(regexp_replace(regexp_replace(regexp_replace(lower(coalesce(aliases, '')), '[^a-z0-9\\s]', '', 'g'), '\\m(inc|corp|corporation|ltd|limited|llc|co|company)\\M', '', 'g'), '\\s+', ' ', 'g')) AS ofac_aliases_normalized "
                "FROM source_ofac_sdn_entities WHERE tenant_id = %(tenant_id)s"
                ") "
                "SELECT DISTINCT fda.company_name, sdn.primary_name "
                "FROM fda JOIN sdn "
                "ON fda.fda_normalized = sdn.ofac_primary_normalized "
                "OR sdn.ofac_aliases_normalized LIKE '%' || fda.fda_normalized || '%' "
                "ORDER BY fda.company_name LIMIT 20"
            ),
        },
        {
            "question": "How many FDA warning-letter companies also appear in the OFAC SDN list?",
            "sql": (
                "WITH overlaps AS ("
                "SELECT DISTINCT f.company_name "
                "FROM source_fda_warning_letters f "
                "JOIN source_ofac_sdn_entities s "
                "ON coalesce(nullif(f.company_name_normalized, ''), trim(regexp_replace(regexp_replace(regexp_replace(lower(coalesce(f.company_name, '')), '[^a-z0-9\\s]', '', 'g'), '\\m(inc|corp|corporation|ltd|limited|llc|co|company)\\M', '', 'g'), '\\s+', ' ', 'g'))) "
                "= trim(regexp_replace(regexp_replace(regexp_replace(lower(coalesce(s.primary_name, '')), '[^a-z0-9\\s]', '', 'g'), '\\m(inc|corp|corporation|ltd|limited|llc|co|company)\\M', '', 'g'), '\\s+', ' ', 'g')) "
                "WHERE f.tenant_id = %(tenant_id)s AND s.tenant_id = %(tenant_id)s"
                ") "
                "SELECT COUNT(*) AS overlap_count FROM overlaps"
            ),
        },
    ],
}


def render_route_guidance(route: str) -> str:
    guidance = ROUTE_GUIDANCE.get(route, [])
    if not guidance:
        return ""
    sections = ["Route-specific guidance:"]
    sections.extend(f"- {line}" for line in guidance)
    return "\n".join(sections)


def render_route_examples(route: str) -> str:
    examples = ROUTE_EXAMPLES.get(route, [])
    if not examples:
        return ""
    sections = ["Examples:"]
    for idx, example in enumerate(examples, start=1):
        sections.append(f"Example {idx} question: {example['question']}")
        sections.append(f"Example {idx} SQL: {example['sql']}")
    return "\n".join(sections)


