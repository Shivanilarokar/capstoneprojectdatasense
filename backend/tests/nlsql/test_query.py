from __future__ import annotations

from unittest import TestCase
from unittest.mock import patch

from backend.nlsql.classifier import ClassificationResult
from backend.config import AppConfig, PROJECT_ROOT
from backend.nlsql.models import QueryExecutionResult, SqlGenerationResult, ValidationResult
from backend.nlsql.query import run_nlsql_query


class NlSqlQueryTests(TestCase):
    def _settings(self) -> AppConfig:
        return AppConfig(
            project_root=PROJECT_ROOT,
            openai_api_key="sk-test",
            openai_model="gpt-4.1-mini",
            pageindex_api_key="",
            neo4j_uri="bolt://localhost:7687",
            neo4j_username="neo4j",
            neo4j_password="password",
            neo4j_database="neo4j",
            graph_tenant_id="tenant-dev",
            sanctions_audit_log=PROJECT_ROOT / "tmp" / "audit.jsonl",
            pg_host="server",
            pg_user="user",
            pg_port=5432,
            pg_database="postgres",
            pg_sslmode="require",
            pg_connect_timeout=15,
            azure_postgres_scope="scope",
        )

    @patch("backend.nlsql.query.synthesize_answer")
    @patch("backend.nlsql.query.classify_question")
    @patch("backend.nlsql.query.run_validated_sql")
    @patch("backend.nlsql.query.validate_generated_sql")
    @patch("backend.nlsql.query.generate_sql")
    @patch("backend.nlsql.query.load_schema_context")
    @patch("backend.nlsql.query.connect_postgres")
    def test_run_nlsql_query_handles_cross_source_question(
        self,
        connect_postgres_mock,
        load_schema_mock,
        generate_sql_mock,
        validate_mock,
        run_sql_mock,
        classify_mock,
        synthesize_mock,
    ) -> None:
        _conn = connect_postgres_mock.return_value.__enter__.return_value
        load_schema_mock.return_value = (
            {"source_ofac_sdn_entities": [], "source_fda_warning_letters": []},
            "Table: source_ofac_sdn_entities\nTable: source_fda_warning_letters",
        )
        classify_mock.return_value = ClassificationResult(
            route="cross_source",
            reason="matched fda and sanctions keywords",
            preferred_tables=["source_fda_warning_letters", "source_ofac_sdn_entities"],
        )
        generate_sql_mock.return_value = SqlGenerationResult(
            reasoning="join sanctions and warnings",
            tables=["source_ofac_sdn_entities", "source_fda_warning_letters"],
            sql="SELECT 1 WHERE tenant_id = %(tenant_id)s",
            ambiguity=False,
        )
        validate_mock.return_value = ValidationResult(ok=True)
        run_sql_mock.return_value = QueryExecutionResult(
            sql="SELECT 1 WHERE tenant_id = %(tenant_id)s",
            rows=[{"company_name": "Acme"}],
            error="",
            repaired=False,
        )
        synthesize_mock.return_value = "Acme appears in the joined result."

        result = run_nlsql_query(
            self._settings(),
            "Which sanctioned entities also appear in FDA warning letters?",
        )

        self.assertEqual("Acme appears in the joined result.", result["answer"])
        self.assertEqual(
            ["source_ofac_sdn_entities", "source_fda_warning_letters"],
            result["generation"]["tables"],
        )
        self.assertEqual("cross_source", result["classification"]["route"])
        self.assertEqual({"tenant_id": "tenant-dev"}, result["execution"]["params"])
        self.assertEqual(1, result["execution"]["row_count"])
        self.assertIn("Question", result["rendered_output"])
        self.assertIn("How It Was Computed", result["rendered_output"])
        run_sql_mock.assert_called_once_with(
            conn=connect_postgres_mock.return_value.__enter__.return_value,
            sql="SELECT 1 WHERE tenant_id = %(tenant_id)s",
            params={"tenant_id": "tenant-dev"},
        )
        self.assertIn("normalized company-name", generate_sql_mock.call_args.args[1].lower())

    @patch("backend.nlsql.query.synthesize_answer", return_value="Texas had the highest loss.")
    @patch("backend.nlsql.query.classify_question")
    @patch("backend.nlsql.query.validate_generated_sql")
    @patch("backend.nlsql.query.generate_sql")
    @patch("backend.nlsql.query.load_schema_context")
    @patch("backend.nlsql.query.connect_postgres")
    @patch("backend.nlsql.query.run_validated_sql")
    def test_run_nlsql_query_repairs_one_failed_sql(
        self,
        run_sql_mock,
        connect_mock,
        schema_mock,
        generate_mock,
        validate_mock,
        classify_mock,
        _synthesize_mock,
    ) -> None:
        schema_mock.return_value = (
            {"source_noaa_storm_events": []},
            "Table: source_noaa_storm_events",
        )
        classify_mock.return_value = ClassificationResult(
            route="weather",
            reason="matched weather keywords",
            preferred_tables=["source_noaa_storm_events"],
        )
        generate_mock.side_effect = [
            SqlGenerationResult(
                reasoning="bad first query",
                tables=["source_noaa_storm_events"],
                sql="SELECT damage_total FROM source_noaa_storm_events WHERE tenant_id = %(tenant_id)s",
                ambiguity=False,
            ),
            SqlGenerationResult(
                reasoning="fixed query",
                tables=["source_noaa_storm_events"],
                sql=(
                    "SELECT state, SUM(damage_property_usd) AS total_damage "
                    "FROM source_noaa_storm_events "
                    "WHERE tenant_id = %(tenant_id)s "
                    "GROUP BY state ORDER BY total_damage DESC LIMIT 5"
                ),
                ambiguity=False,
            ),
        ]
        validate_mock.return_value = ValidationResult(ok=True)
        run_sql_mock.side_effect = [
            QueryExecutionResult(
                sql="SELECT damage_total FROM source_noaa_storm_events WHERE tenant_id = %(tenant_id)s",
                rows=[],
                error='column "damage_total" does not exist',
                repaired=False,
            ),
            QueryExecutionResult(
                sql=(
                    "SELECT state, SUM(damage_property_usd) AS total_damage "
                    "FROM source_noaa_storm_events "
                    "WHERE tenant_id = %(tenant_id)s "
                    "GROUP BY state ORDER BY total_damage DESC LIMIT 5"
                ),
                rows=[{"state": "Texas", "total_damage": 1200.0}],
                error="",
                repaired=False,
            ),
        ]

        result = run_nlsql_query(self._settings(), "Which states had the highest property damage?")

        self.assertEqual("Texas had the highest loss.", result["answer"])
        self.assertTrue(result["execution"]["repaired"])
        self.assertEqual("weather", result["classification"]["route"])
        self.assertEqual({"tenant_id": "tenant-dev"}, result["execution"]["params"])
        self.assertEqual(1, result["execution"]["row_count"])
        self.assertEqual(2, generate_mock.call_count)
        self.assertIn("Evidence", result["rendered_output"])

    @patch("backend.nlsql.query.synthesize_answer", return_value="Texas had the highest loss.")
    @patch("backend.nlsql.query.classify_question")
    @patch("backend.nlsql.query.validate_generated_sql")
    @patch("backend.nlsql.query.generate_sql")
    @patch("backend.nlsql.query.load_schema_context")
    @patch("backend.nlsql.query.connect_postgres")
    @patch("backend.nlsql.query.run_validated_sql")
    def test_run_nlsql_query_repairs_validation_failure(
        self,
        run_sql_mock,
        connect_mock,
        schema_mock,
        generate_mock,
        validate_mock,
        classify_mock,
        _synthesize_mock,
    ) -> None:
        schema_mock.return_value = (
            {"source_noaa_storm_events": [{"column_name": "tenant_id"}]},
            "Table: source_noaa_storm_events\n- tenant_id (text)\n- state (text)",
        )
        classify_mock.return_value = ClassificationResult(
            route="weather",
            reason="matched weather keywords",
            preferred_tables=["source_noaa_storm_events"],
        )
        generate_mock.side_effect = [
            SqlGenerationResult(
                reasoning="missing tenant filter",
                tables=["source_noaa_storm_events"],
                sql="SELECT state FROM source_noaa_storm_events",
                ambiguity=False,
            ),
            SqlGenerationResult(
                reasoning="fixed tenant filter",
                tables=["source_noaa_storm_events"],
                sql=(
                    "SELECT state, SUM(damage_property_usd) AS total_damage "
                    "FROM source_noaa_storm_events "
                    "WHERE tenant_id = %(tenant_id)s "
                    "GROUP BY state ORDER BY total_damage DESC LIMIT 5"
                ),
                ambiguity=False,
            ),
        ]
        validate_mock.side_effect = [
            ValidationResult(ok=False, reason="SQL must filter source_noaa_storm_events by tenant_id."),
            ValidationResult(ok=True),
        ]
        run_sql_mock.return_value = QueryExecutionResult(
            sql=(
                "SELECT state, SUM(damage_property_usd) AS total_damage "
                "FROM source_noaa_storm_events "
                "WHERE tenant_id = %(tenant_id)s "
                "GROUP BY state ORDER BY total_damage DESC LIMIT 5"
            ),
            rows=[{"state": "Texas", "total_damage": 1200.0}],
            error="",
            repaired=False,
        )

        result = run_nlsql_query(self._settings(), "Which states had the highest property damage?")

        self.assertEqual("Texas had the highest loss.", result["answer"])
        self.assertTrue(result["execution"]["repaired"])
        self.assertEqual(2, generate_mock.call_count)
        self.assertIn("debug_payload", result)




