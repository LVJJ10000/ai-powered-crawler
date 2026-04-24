import pathlib
import unittest


class TestRepoLayout(unittest.TestCase):
    def test_internal_plans_live_under_superpowers_docs(self):
        root = pathlib.Path(__file__).resolve().parents[1]
        specs_dir = root / "docs" / "superpowers" / "specs"

        self.assertFalse((root / "OOP_AI_XPATH_REFACTOR_PLAN.md").exists())
        self.assertFalse((root / "PAGINATION_ENGINE_REFACTOR_PLAN.md").exists())
        self.assertFalse((root / "SOLUTION_PLAN.md").exists())

        self.assertTrue(specs_dir.is_dir())
        self.assertTrue(
            (specs_dir / "2026-04-24-depth-traversal-design.md").exists()
        )


if __name__ == "__main__":
    unittest.main()
