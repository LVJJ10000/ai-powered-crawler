import pathlib
import subprocess
import unittest


class TestRepoLayout(unittest.TestCase):
    def test_tracked_markdown_layout_keeps_public_root_docs_only(self):
        root = pathlib.Path(__file__).resolve().parents[1]
        tracked_files = subprocess.run(
            ["git", "ls-files", "*.md"],
            check=True,
            cwd=root,
            capture_output=True,
            text=True,
        ).stdout.splitlines()
        tracked_root_markdown = {
            path for path in tracked_files if "/" not in path
        }
        tracked_spec_docs = [
            path
            for path in tracked_files
            if path.startswith("docs/superpowers/specs/") and path.endswith(".md")
        ]
        allowed_root_markdown = {
            "README.md",
            "CONTRIBUTING.md",
            "CODE_OF_CONDUCT.md",
            "SECURITY.md",
        }
        legacy_plan_docs = {
            "OOP_AI_XPATH_REFACTOR_PLAN.md",
            "PAGINATION_ENGINE_REFACTOR_PLAN.md",
            "SOLUTION_PLAN.md",
        }

        for legacy_name in legacy_plan_docs:
            self.assertFalse((root / legacy_name).exists())
        self.assertSetEqual(tracked_root_markdown, allowed_root_markdown)
        self.assertTrue(tracked_spec_docs)


if __name__ == "__main__":
    unittest.main()
