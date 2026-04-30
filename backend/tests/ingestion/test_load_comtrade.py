from __future__ import annotations

from unittest import TestCase

from backend.ingestion.load_comtrade import transform_comtrade_row


class ComtradeLoaderTests(TestCase):
    def test_transform_comtrade_row_maps_trade_dimensions(self) -> None:
        row = {
            "typeCode": "C",
            "freqCode": "A",
            "refPeriodId": 20250101,
            "refYear": 2025,
            "refMonth": 52,
            "period": "2025",
            "reporterCode": 31,
            "flowCode": "X",
            "flowDesc": "Export",
            "reporterISO": "AZE",
            "reporterDesc": "Azerbaijan",
            "partnerCode": 0,
            "partnerISO": "W00",
            "partnerDesc": "World",
            "partner2Code": 0,
            "partner2ISO": "W00",
            "partner2Desc": "World",
            "classificationCode": "H6",
            "classificationSearchCode": "HS",
            "isOriginalClassification": True,
            "cmdCode": "TOTAL",
            "cmdDesc": "All Commodities",
            "aggrLevel": 0,
            "isLeaf": False,
            "customsCode": "C00",
            "customsDesc": "TOTAL CPC",
            "mosCode": "0",
            "motCode": 0,
            "motDesc": "TOTAL MOT",
            "qtyUnitCode": -1,
            "qtyUnitAbbr": "N/A",
            "qty": 0,
            "isQtyEstimated": False,
            "altQtyUnitCode": -1,
            "altQtyUnitAbbr": "N/A",
            "altQty": 0,
            "isAltQtyEstimated": False,
            "netWgt": None,
            "isNetWgtEstimated": False,
            "grossWgt": 0,
            "isGrossWgtEstimated": False,
            "cifvalue": None,
            "fobvalue": 25042007312.55,
            "primaryValue": 25042007312.55,
            "legacyEstimationFlag": 0,
            "isReported": False,
            "isAggregate": True,
        }

        record = transform_comtrade_row("tenant-dev", "TradeData.xlsx", row)

        self.assertEqual("C", record["type_code"])
        self.assertEqual("A", record["freq_code"])
        self.assertEqual(20250101, record["ref_period_id"])
        self.assertEqual(2025, record["ref_year"])
        self.assertEqual(52, record["ref_month"])
        self.assertEqual(31, record["reporter_code"])
        self.assertEqual("X", record["flow_code"])
        self.assertEqual("AZE", record["reporter_iso"])
        self.assertEqual(0, record["partner_code"])
        self.assertEqual("H6", record["classification_code"])
        self.assertTrue(record["is_original_classification"])
        self.assertEqual(0, record["aggr_level"])
        self.assertFalse(record["is_leaf"])
        self.assertEqual(-1, record["qty_unit_code"])
        self.assertFalse(record["is_qty_estimated"])
        self.assertEqual(0.0, record["gross_wgt"])
        self.assertTrue(record["is_aggregate"])
        self.assertEqual(25042007312.55, record["primary_value"])
        self.assertEqual("TO", record["cmd_code_level2"])
        self.assertEqual("TOTA", record["cmd_code_level4"])
        self.assertEqual("TOTAL", record["cmd_code_level6"])



