from __future__ import annotations

from pathlib import Path
from unittest import TestCase
from unittest.mock import MagicMock

from config import PROJECT_ROOT
from ingestion.cli import SourceSpec, load_records_into_table, parse_args, selected_sources


class IngestionCliTests(TestCase):
    def test_parse_args_supports_all_source_bootstrap(self) -> None:
        args = parse_args(["--source", "all", "--tenant-id", "tenant-dev", "--init-schema"])
        self.assertEqual("all", args.source)
        self.assertEqual("tenant-dev", args.tenant_id)
        self.assertTrue(args.init_schema)

    def test_selected_sources_expands_all_in_stable_order(self) -> None:
        self.assertEqual(
            ["ofac_bis", "noaa", "fda", "comtrade"],
            [spec.name for spec in selected_sources("all")],
        )

    def test_selected_sources_point_to_data_ingestion_root(self) -> None:
        specs = selected_sources("all")
        self.assertTrue(
            all("data/ingestion" in str(spec.relative_path).replace("\\", "/") for spec in specs)
        )

    def test_load_records_into_table_executes_upsert_batches(self) -> None:
        conn = MagicMock()
        cursor = conn.cursor.return_value.__enter__.return_value

        loaded = load_records_into_table(
            conn=conn,
            table_name="source_fda_warning_letters",
            conflict_columns=["tenant_id", "source_record_hash"],
            records=[
                {
                    "tenant_id": "tenant-dev",
                    "source_record_hash": "abc",
                    "company_name": "Acme Labs",
                },
                {
                    "tenant_id": "tenant-dev",
                    "source_record_hash": "def",
                    "company_name": "Globex",
                },
            ],
            batch_size=1,
        )

        self.assertEqual(2, loaded)
        self.assertEqual(2, cursor.executemany.call_count)
        self.assertIn(
            "INSERT INTO source_fda_warning_letters",
            cursor.executemany.call_args.args[0],
        )

    def test_source_spec_resolve_path_falls_back_to_available_file_in_directory(self) -> None:
        project_root = PROJECT_ROOT / "tmp" / "test-ingestion-cli-project"
        source_dir = project_root / "data" / "ingestion" / "noaa"
        source_dir.mkdir(parents=True, exist_ok=True)
        actual_file = source_dir / "StormEvents_details-ftp_v1.0_d1950_c20260323.csv"
        actual_file.write_text("EVENT_ID\n1\n", encoding="utf-8")

        spec = SourceSpec(
            name="noaa",
            table_name="source_noaa_storm_events",
            conflict_columns=("tenant_id", "event_id"),
            relative_path=Path("data/ingestion/noaa/StormEvents_details-ftp_v1.0_d2025_c20250717.csv"),
            iterator_factory=object(),
        )

        resolved = spec.resolve_path(project_root)

        self.assertEqual(actual_file.resolve(), resolved)

    def test_legacy_ingestion_sql_surface_is_removed(self) -> None:
        self.assertFalse((PROJECT_ROOT / "src" / "ingestion_sql").exists())
        self.assertFalse((PROJECT_ROOT / "run_ingestion_sql.py").exists())
