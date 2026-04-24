import pathlib
import unittest


class TestRepoLayout(unittest.TestCase):
    def test_markdown_docs_live_under_superpowers_tree(self):
        root = pathlib.Path(__file__).resolve().parents[1]
        docs_dir = root / "docs"
        markdown_docs = list(docs_dir.rglob("*.md"))

        self.assertFalse((root / "OOP_AI_XPATH_REFACTOR_PLAN.md").exists())
        self.assertFalse((root / "PAGINATION_ENGINE_REFACTOR_PLAN.md").exists())
        self.assertFalse((root / "SOLUTION_PLAN.md").exists())

        self.assertTrue(markdown_docs)
        for doc_path in markdown_docs:
            self.assertEqual(
                doc_path.relative_to(docs_dir).parts[0],
                "superpowers",
                f"unexpected markdown doc outside docs/superpowers: {doc_path}",
            )


if __name__ == "__main__":
    unittest.main()
