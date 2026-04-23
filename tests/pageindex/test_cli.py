from __future__ import annotations

from pathlib import Path
from unittest import TestCase
from unittest.mock import patch

from pageindex.cli import parse_args


class PageIndexCliTests(TestCase):
    @patch("sys.argv", ["run_pageindex_pipeline.py"])
    def test_parse_args_defaults_to_data_artifact_directories(self) -> None:
        args = parse_args()

        self.assertEqual(Path("data/pageindex/docs"), Path(args.docs_dir))
        self.assertEqual(Path("data/pageindex/workspace"), Path(args.workspace))
        self.assertEqual(Path("data/pageindex/output"), Path(args.output_dir))
