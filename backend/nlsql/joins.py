from __future__ import annotations


def normalized_company_expression(column_sql: str) -> str:
    return (
        "trim(regexp_replace("
        "regexp_replace("
        f"regexp_replace(lower(coalesce({column_sql}, '')), '[^a-z0-9\\s]', '', 'g'), "
        "'\\m(inc|corp|corporation|ltd|limited|llc|co|company)\\M', '', 'g'"
        "), "
        "'\\s+', ' ', 'g'"
        "))"
    )


def normalized_alias_blob_expression(column_sql: str) -> str:
    return normalized_company_expression(column_sql)


def helper_text_for_route(route: str) -> str:
    if route != "cross_source":
        return ""
    fda_expr = (
        "coalesce(nullif(company_name_normalized, ''), "
        f"{normalized_company_expression('company_name')})"
    )
    ofac_expr = normalized_company_expression("primary_name")
    alias_expr = normalized_alias_blob_expression("aliases")
    return (
        "Cross-source helper for deterministic normalized-name matching:\n"
        "- Table A: source_fda_warning_letters\n"
        "- Table B: source_ofac_sdn_entities\n"
        "- Prefer company_name_normalized from FDA when present.\n"
        "- Use deterministic normalized company-name matching rather than raw equality.\n"
        "- Match FDA normalized names against OFAC primary names first, then aliases text when needed.\n"
        f"- FDA normalized expression: {fda_expr}\n"
        f"- OFAC normalized expression: {ofac_expr}\n"
        f"- OFAC aliases normalized expression: {alias_expr}\n"
        "- Suggested join predicate: fda_normalized = ofac_primary_normalized "
        "OR ofac_aliases_normalized LIKE '%' || fda_normalized || '%'\n"
        "- Keep tenant_id filters on both tables."
    )


