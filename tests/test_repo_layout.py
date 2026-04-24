import pathlib
import unittest


class TestRepoLayout(unittest.TestCase):
    def test_internal_plans_are_archived(self):
        root = pathlib.Path(__file__).resolve().parents[1]
        archive = root / "docs" / "archive"

        self.assertTrue((archive / "OOP_AI_XPATH_REFACTOR_PLAN.md").exists())
        self.assertTrue((archive / "PAGINATION_ENGINE_REFACTOR_PLAN.md").exists())
        self.assertTrue((archive / "SOLUTION_PLAN.md").exists())

        self.assertFalse((root / "OOP_AI_XPATH_REFACTOR_PLAN.md").exists())
        self.assertFalse((root / "PAGINATION_ENGINE_REFACTOR_PLAN.md").exists())
        self.assertFalse((root / "SOLUTION_PLAN.md").exists())


if __name__ == "__main__":
    unittest.main()
