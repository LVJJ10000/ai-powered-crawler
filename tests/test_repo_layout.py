import pathlib
import subprocess
import unittest


class TestRepoLayout(unittest.TestCase):
    def test_tracked_internal_spec_docs_live_under_superpowers_specs(self):
        root = pathlib.Path(__file__).resolve().parents[1]
        tracked_files = subprocess.run(
            ["git", "ls-files", "docs/superpowers/specs"],
            check=True,
            cwd=root,
            capture_output=True,
            text=True,
        ).stdout.splitlines()
        tracked_spec_docs = [
            path for path in tracked_files if path.endswith(".md")
        ]

        self.assertFalse((root / "OOP_AI_XPATH_REFACTOR_PLAN.md").exists())
        self.assertFalse((root / "PAGINATION_ENGINE_REFACTOR_PLAN.md").exists())
        self.assertFalse((root / "SOLUTION_PLAN.md").exists())

        self.assertTrue(tracked_spec_docs)
        for tracked_path in tracked_spec_docs:
            self.assertTrue(
                tracked_path.startswith("docs/superpowers/specs/"),
                f"unexpected tracked spec doc path: {tracked_path}",
            )


if __name__ == "__main__":
    unittest.main()
