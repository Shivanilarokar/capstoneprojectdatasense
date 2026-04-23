from __future__ import annotations

APPROVED_TABLES = (
    "source_ofac_bis_entities",
    "source_noaa_storm_events",
    "source_fda_warning_letters",
    "source_comtrade_flows",
)


def load_approved_schema(conn) -> dict[str, list[dict]]:
    sql = """
    SELECT table_name, column_name, data_type
    FROM information_schema.columns
    WHERE table_schema = 'public'
      AND table_name = ANY(%(table_names)s)
    ORDER BY table_name, ordinal_position
    """
    with conn.cursor() as cur:
        cur.execute(sql, {"table_names": list(APPROVED_TABLES)})
        rows = cur.fetchall()

    schema: dict[str, list[dict]] = {table: [] for table in APPROVED_TABLES}
    for row in rows:
        schema[row["table_name"]].append(
            {"column_name": row["column_name"], "data_type": row["data_type"]}
        )
    return {table: columns for table, columns in schema.items() if columns}


def format_schema_for_prompt(schema: dict[str, list[dict]]) -> str:
    sections: list[str] = []
    for table_name, columns in schema.items():
        sections.append(f"Table: {table_name}")
        for column in columns:
            sections.append(f"- {column['column_name']} ({column['data_type']})")
    return "\n".join(sections)
