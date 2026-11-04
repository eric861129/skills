from __future__ import annotations

import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = REPOSITORY_ROOT / "skills" / "organize-files" / "scripts"


def run(script: str, *args: str, env: dict[str, str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-B", str(SCRIPTS / script), *args],
        capture_output=True, text=True, encoding="utf-8", env=env, check=False,
    )


def snapshot(root: Path) -> dict[str, bytes]:
    return {
        path.relative_to(root).as_posix(): path.read_bytes()
        for path in sorted(root.rglob("*")) if path.is_file()
    }


class OrganizeFilesTests(unittest.TestCase):
    def setUp(self) -> None:
        self.base = Path(tempfile.mkdtemp(prefix="organize-files-test-"))
        self.root = self.base / "root"
        self.logs = self.base / "logs"
        (self.root / "sub").mkdir(parents=True)
        (self.root / "repo" / ".git").mkdir(parents=True)
        (self.root / "Images").mkdir()
        (self.root / "Documents").mkdir()
        (self.root / "a.jpg").write_text("same", encoding="utf-8")
        (self.root / "sub" / "copy.jpg").write_text("same", encoding="utf-8")
        (self.root / "Images" / "copy.jpg").write_text("same", encoding="utf-8")
        (self.root / "report.pdf").write_text("new", encoding="utf-8")
        (self.root / "Documents" / "report.pdf").write_text("old!", encoding="utf-8")
        (self.root / "repo" / "main.py").write_text("print()", encoding="utf-8")
        self.env = {**os.environ, "ORGANIZE_FILES_LOG_DIR": str(self.logs), "PYTHONIOENCODING": "utf-8"}

    def tearDown(self) -> None:
        shutil.rmtree(self.base, ignore_errors=True)

    def inventory(self) -> dict:
        result = run("inventory_files.py", str(self.root), env=self.env)
        self.assertEqual(result.returncode, 0, result.stderr)
        return json.loads(result.stdout)

    def write_manifest(self, run_dir: Path, operations: list[dict], approved: bool = True) -> None:
        manifest = {
            "schema_version": "1.0",
            "root": str(self.root),
            "options": {"remove_emptied_dirs": True},
            "approval": {"approved_by_user": approved},
            "operations": operations,
        }
        (run_dir / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")

    def test_inventory_is_read_only_and_finds_units_and_duplicates(self) -> None:
        before = snapshot(self.root)
        data = self.inventory()
        self.assertEqual(snapshot(self.root), before)
        run_dir = Path(data["run_dir"])
        self.assertTrue(run_dir.is_relative_to(self.logs))
        self.assertTrue((run_dir / "inventory.json").exists())
        self.assertTrue((run_dir / "tree-before.txt").exists())
        self.assertNotIn("files", data)
        self.assertEqual([u["path"] for u in data["atomic_units"]], ["repo"])
        self.assertEqual(
            data["duplicates"][0]["paths"], ["a.jpg", "Images/copy.jpg", "sub/copy.jpg"]
        )

    def test_run_dir_none_writes_nothing(self) -> None:
        result = run("inventory_files.py", str(self.root), "--run-dir", "none", "--format", "json", env=self.env)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertFalse(self.logs.exists())
        self.assertIn("files", json.loads(result.stdout))

    def test_validation_rejects_delete_and_moves_inside_units(self) -> None:
        run_dir = Path(self.inventory()["run_dir"])
        self.write_manifest(run_dir, [
            {"id": 1, "op": "delete", "src": "a.jpg"},
            {"id": 2, "op": "move", "src": "repo/main.py", "dst": "Code/main.py"},
            {"id": 3, "op": "move", "src": "a.jpg", "dst": "../outside.jpg"},
        ])
        result = run("apply_manifest.py", str(run_dir), env=self.env)
        self.assertEqual(result.returncode, 1)
        errors = " ".join(json.loads(result.stdout)["errors"])
        self.assertIn("deleting is not allowed", errors)
        self.assertIn("atomic unit", errors)
        self.assertIn("outside root", errors)

    def test_execute_requires_approval(self) -> None:
        run_dir = Path(self.inventory()["run_dir"])
        self.write_manifest(run_dir, [{"id": 1, "op": "move", "src": "a.jpg", "dst": "Images/a.jpg"}], approved=False)
        before = snapshot(self.root)
        result = run("apply_manifest.py", str(run_dir), "--execute", env=self.env)
        self.assertEqual(result.returncode, 3)
        self.assertEqual(snapshot(self.root), before)

    def test_execute_stages_duplicates_suffixes_conflicts_and_undo_restores(self) -> None:
        before = snapshot(self.root)
        run_dir = Path(self.inventory()["run_dir"])
        self.write_manifest(run_dir, [
            {"id": 1, "op": "move", "src": "a.jpg", "dst": "Images/a.jpg"},
            {"id": 2, "op": "move", "src": "sub/copy.jpg", "dst": "Images/copy.jpg"},
            {"id": 3, "op": "move", "src": "report.pdf", "dst": "Documents/report.pdf"},
            {"id": 4, "op": "move", "src": "repo", "dst": "Projects/repo"},
        ])
        dry = run("apply_manifest.py", str(run_dir), env=self.env)
        self.assertEqual(dry.returncode, 0, dry.stdout + dry.stderr)
        self.assertEqual(snapshot(self.root), before)

        result = run("apply_manifest.py", str(run_dir), "--execute", env=self.env)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        summary = json.loads(result.stdout)
        self.assertEqual(summary["status_counts"], {"done": 3, "staged": 1})
        staging = self.root / "_organize-staging" / run_dir.name
        self.assertTrue((staging / "sub" / "copy.jpg").exists())
        self.assertTrue((self.root / "Documents" / "report (2).pdf").exists())
        self.assertTrue((self.root / "Projects" / "repo" / "main.py").exists())
        self.assertFalse((self.root / "sub").exists())  # emptied and approved for removal
        self.assertTrue((run_dir / "tree-after.txt").exists())
        # Nothing was deleted: every original byte string still exists somewhere.
        self.assertEqual(sorted(snapshot(self.root).values()), sorted(before.values()))

        undo = run("undo.py", str(run_dir), "--execute", env=self.env)
        self.assertEqual(undo.returncode, 0, undo.stdout + undo.stderr)
        self.assertEqual(snapshot(self.root), before)
        self.assertFalse((self.root / "_organize-staging").exists())
        self.assertTrue((self.root / "sub").is_dir())

    @unittest.skipUnless(os.name == "nt", "Windows sharing violations block renames of open files")
    def test_locked_file_is_skipped_then_retried(self) -> None:
        run_dir = Path(self.inventory()["run_dir"])
        self.write_manifest(run_dir, [
            {"id": 1, "op": "move", "src": "a.jpg", "dst": "Images/a.jpg"},
            {"id": 2, "op": "move", "src": "report.pdf", "dst": "Docs/report.pdf"},
        ])
        handle = (self.root / "a.jpg").open("rb")
        try:
            result = run("apply_manifest.py", str(run_dir), "--execute", "--retry-delays", "0", env=self.env)
        finally:
            handle.close()
        self.assertEqual(result.returncode, 4, result.stdout + result.stderr)
        summary = json.loads(result.stdout)
        self.assertEqual(summary["status_counts"], {"locked": 1, "done": 1})
        self.assertTrue((self.root / "a.jpg").exists())
        self.assertTrue(summary["needs_attention"][0]["holders"])

        retry = run("apply_manifest.py", str(run_dir), "--retry-failed", "--retry-delays", "0", env=self.env)
        self.assertEqual(retry.returncode, 0, retry.stdout + retry.stderr)
        retry_summary = json.loads(retry.stdout)
        self.assertEqual(retry_summary["attempted_this_run"], 1)
        self.assertTrue((self.root / "Images" / "a.jpg").exists())


if __name__ == "__main__":
    unittest.main()
