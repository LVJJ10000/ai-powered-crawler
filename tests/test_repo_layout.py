import pathlib
import unittest


class TestRepoLayout(unittest.TestCase):
    def test_internal_spec_docs_live_under_superpowers_docs(self):
        root = pathlib.Path(__file__).resolve().parents[1]
        specs_dir = root / "docs" / "superpowers" / "specs"

        self.assertFalse((root / "OOP_AI_XPATH_REFACTOR_PLAN.md").exists())
        self.assertFalse((root / "PAGINATION_ENGINE_REFACTOR_PLAN.md").exists())
        self.assertFalse((root / "SOLUTION_PLAN.md").exists())

        self.assertTrue(specs_dir.is_dir())
        self.assertTrue(list(specs_dir.glob("*-design.md")))


if __name__ == "__main__":
    unittest.main()
