from __future__ import annotations

import tomllib
from pathlib import Path
from unittest import TestCase

from backend.config import PROJECT_ROOT


class DependencyMetadataTests(TestCase):
    def test_pyproject_and_requirements_match_runtime_dependencies(self) -> None:
        pyproject = tomllib.loads((PROJECT_ROOT / "pyproject.toml").read_text(encoding="utf-8"))
        pyproject_deps = list(pyproject["project"]["dependencies"])
        requirements = [
            line.strip()
            for line in (PROJECT_ROOT / "requirements.txt").read_text(encoding="utf-8").splitlines()
            if line.strip() and not line.strip().startswith("#")
        ]

        self.assertEqual(pyproject_deps, requirements)

    def test_required_runtime_packages_are_declared(self) -> None:
        pyproject = tomllib.loads((PROJECT_ROOT / "pyproject.toml").read_text(encoding="utf-8"))
        deps = set(pyproject["project"]["dependencies"])

        self.assertTrue(any(dep.startswith("pydantic==") for dep in deps))
        self.assertTrue(any(dep.startswith("PyMuPDF==") for dep in deps))
        self.assertTrue(any(dep.startswith("python-dotenv==") for dep in deps))



