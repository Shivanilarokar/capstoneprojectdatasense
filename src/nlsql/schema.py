from __future__ import annotations

SOURCE_TABLE_DDLS = {
    "source_ofac_bis_entities": """
        CREATE TABLE IF NOT EXISTS source_ofac_bis_entities (
            tenant_id TEXT NOT NULL,
            source_entity_id TEXT NOT NULL,
            primary_name TEXT NOT NULL,
            entity_type TEXT,
            sanctions_programs TEXT,
            sanctions_type TEXT,
            date_published TEXT,
            aliases TEXT,
            nationality TEXT,
            citizenship TEXT,
            address_text TEXT,
            document_ids TEXT,
            source_file_name TEXT NOT NULL,
            source_loaded_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            raw_payload JSONB NOT NULL,
            PRIMARY KEY (tenant_id, source_entity_id)
        )
    """,
    "source_comtrade_flows": """
        CREATE TABLE IF NOT EXISTS source_comtrade_flows (
            tenant_id TEXT NOT NULL,
            source_record_hash TEXT NOT NULL,
            ref_year INTEGER NOT NULL,
            flow_code TEXT,
            flow_desc TEXT,
            reporter_iso TEXT,
            reporter_desc TEXT,
            partner_iso TEXT,
            partner_desc TEXT,
            cmd_code TEXT,
            cmd_desc TEXT,
            qty DOUBLE PRECISION,
            net_wgt DOUBLE PRECISION,
            cifvalue DOUBLE PRECISION,
            fobvalue DOUBLE PRECISION,
            primary_value DOUBLE PRECISION,
            source_file_name TEXT NOT NULL,
            source_loaded_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            raw_payload JSONB NOT NULL,
            PRIMARY KEY (tenant_id, source_record_hash)
        )
    """,
    "source_noaa_storm_events": """
        CREATE TABLE IF NOT EXISTS source_noaa_storm_events (
            tenant_id TEXT NOT NULL,
            event_id BIGINT NOT NULL,
            episode_id BIGINT,
            state TEXT,
            year INTEGER,
            month_name TEXT,
            event_type TEXT,
            cz_name TEXT,
            begin_date_time TEXT,
            end_date_time TEXT,
            damage_property_raw TEXT,
            damage_property_usd DOUBLE PRECISION,
            damage_crops_raw TEXT,
            damage_crops_usd DOUBLE PRECISION,
            begin_lat DOUBLE PRECISION,
            begin_lon DOUBLE PRECISION,
            end_lat DOUBLE PRECISION,
            end_lon DOUBLE PRECISION,
            episode_narrative TEXT,
            event_narrative TEXT,
            source_file_name TEXT NOT NULL,
            source_loaded_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            raw_payload JSONB NOT NULL,
            PRIMARY KEY (tenant_id, event_id)
        )
    """,
    "source_fda_warning_letters": """
        CREATE TABLE IF NOT EXISTS source_fda_warning_letters (
            tenant_id TEXT NOT NULL,
            source_record_hash TEXT NOT NULL,
            posted_date TEXT,
            letter_issue_date TEXT,
            company_name TEXT NOT NULL,
            issuing_office TEXT,
            subject TEXT,
            response_letter TEXT,
            closeout_letter TEXT,
            source_file_name TEXT NOT NULL,
            source_loaded_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            raw_payload JSONB NOT NULL,
            PRIMARY KEY (tenant_id, source_record_hash)
        )
    """,
}


def ensure_source_tables(conn) -> None:
    with conn.cursor() as cur:
        for ddl in SOURCE_TABLE_DDLS.values():
            cur.execute(ddl)
