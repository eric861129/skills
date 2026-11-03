from __future__ import annotations

import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
SCRIPT_PATH = (
    REPOSITORY_ROOT
    / "skills"
    / "consolidate-document-sprawl"
    / "scripts"
    / "inventory_documents.py"
)


class InventoryDocumentsTests(unittest.TestCase):
    def setUp(self) -> None:
        self.root = Path(tempfile.mkdtemp(prefix="open-skills-inventory-"))
        self.docs = self.root / "docs"
        self.generated = self.docs / "generated"
        self.node_modules = self.root / "node_modules"
        self.generated.mkdir(parents=True)
        self.node_modules.mkdir()

        self.created_files = [
            self.docs / "canonical.md",
            self.docs / "duplicate.md",
            self.docs / "links.md",
            self.generated / "api.md",
            self.node_modules / "ignored.md",
        ]

        shared = "# Canonical\n\n唯一內容。\n"
        self.created_files[0].write_text(shared, encoding="utf-8")
        self.created_files[1].write_text(shared, encoding="utf-8")
        self.created_files[2].write_text(
            "# Links\n\n[存在](canonical.md) [遺失](missing.md)\n",
            encoding="utf-8",
        )
        self.created_files[3].write_text(
            "<!-- This file is auto-generated. Do not edit. -->\n# API\n",
            encoding="utf-8",
        )
        self.created_files[4].write_text("# Ignore\n", encoding="utf-8")

        self.before_hashes = {
            path: hashlib.sha256(path.read_bytes()).hexdigest()
            for path in self.created_files
        }

    def tearDown(self) -> None:
        for path in reversed(self.created_files):
            if path.exists():
                path.unlink()
        for directory in [self.generated, self.docs, self.node_modules, self.root]:
            if directory.exists():
                directory.rmdir()

    def run_inventory(self) -> dict[str, object]:
        result = subprocess.run(
            [
                sys.executable,
                str(SCRIPT_PATH),
                str(self.root),
                "--format",
                "json",
            ],
            check=False,
            capture_output=True,
            text=True,
            encoding="utf-8",
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        return json.loads(result.stdout)

    def test_reports_duplicates_links_generated_hints_and_exclusions(self) -> None:
        report = self.run_inventory()

        paths = {item["path"] for item in report["documents"]}
        self.assertEqual(
            paths,
            {
                "docs/canonical.md",
                "docs/duplicate.md",
                "docs/generated/api.md",
                "docs/links.md",
            },
        )
        self.assertEqual(
            report["exact_duplicate_groups"][0]["paths"],
            ["docs/canonical.md", "docs/duplicate.md"],
        )

        links = next(
            item for item in report["documents"] if item["path"] == "docs/links.md"
        )
        self.assertEqual(links["local_links"][0]["status"], "ok")
        self.assertEqual(links["local_links"][1]["status"], "missing")

        generated = next(
            item
            for item in report["documents"]
            if item["path"] == "docs/generated/api.md"
        )
        self.assertIn("generated-path", generated["hints"])
        self.assertIn("generated-marker", generated["hints"])

    def test_is_read_only(self) -> None:
        self.run_inventory()

        after_hashes = {
            path: hashlib.sha256(path.read_bytes()).hexdigest()
            for path in self.created_files
        }
        self.assertEqual(after_hashes, self.before_hashes)


if __name__ == "__main__":
    unittest.main()
