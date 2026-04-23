"""Convenience launcher for syncing structured data into GraphRAG Neo4j state."""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from graphrag.cli_pipeline import main


if __name__ == "__main__":
    main()
