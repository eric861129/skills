from __future__ import annotations

import json
from pathlib import Path
import re
import unittest


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
SKILLS_ROOT = REPOSITORY_ROOT / "skills"
SKILLS = {
    "control-document-growth",
    "consolidate-document-sprawl",
    "finish-project-work",
}


class RepositoryContractsTests(unittest.TestCase):
    def test_eval_catalog_covers_pressure_counterexample_and_boundaries(self) -> None:
        catalog = json.loads(
            (REPOSITORY_ROOT / "evals" / "cases.json").read_text(encoding="utf-8")
        )

        self.assertEqual(catalog["schema_version"], "1.0")
        for skill in SKILLS:
            cases = [case for case in catalog["cases"] if case["skill"] == skill]
            self.assertGreaterEqual(len(cases), 3)
            self.assertTrue(any(case["kind"] == "pressure" for case in cases))
            self.assertTrue(any(case["kind"] != "pressure" for case in cases))
            for case in cases:
                self.assertTrue(case["required_fields"])
                self.assertTrue(case["forbidden_actions"])

    def test_skill_frontmatter_and_interface_metadata_are_valid_utf8(self) -> None:
        for skill in SKILLS:
            skill_text = (SKILLS_ROOT / skill / "SKILL.md").read_text(
                encoding="utf-8"
            )
            interface_text = (
                SKILLS_ROOT / skill / "agents" / "openai.yaml"
            ).read_text(encoding="utf-8")

            self.assertRegex(skill_text, rf"(?m)^name: {re.escape(skill)}$")
            self.assertRegex(skill_text, r"(?m)^description: .+$")
            self.assertIn("display_name:", interface_text)
            self.assertIn("short_description:", interface_text)
            self.assertIn(f"${skill}", interface_text)


if __name__ == "__main__":
    unittest.main()
