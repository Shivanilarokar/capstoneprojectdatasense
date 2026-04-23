from __future__ import annotations

from unittest import TestCase

from ingestion.load_comtrade import transform_comtrade_row


class ComtradeLoaderTests(TestCase):
    def test_transform_comtrade_row_maps_trade_dimensions(self) -> None:
        row = {
            "refYear": 2025,
            "flowCode": "X",
            "flowDesc": "Export",
            "reporterISO": "AZE",
            "reporterDesc": "Azerbaijan",
            "partnerISO": "W00",
            "partnerDesc": "World",
            "cmdCode": "TOTAL",
            "cmdDesc": "All Commodities",
            "qty": 0,
            "netWgt": None,
            "cifvalue": None,
            "fobvalue": 25042007312.55,
            "primaryValue": 25042007312.55,
        }

        record = transform_comtrade_row("tenant-dev", "TradeData.xlsx", row)

        self.assertEqual(2025, record["ref_year"])
        self.assertEqual("X", record["flow_code"])
        self.assertEqual("AZE", record["reporter_iso"])
        self.assertEqual(25042007312.55, record["primary_value"])
