import pathlib
import unittest


class TestCiReleaseLayout(unittest.TestCase):
    def test_ci_compiles_src_tree(self):
        root = pathlib.Path(__file__).resolve().parents[1]
        workflow = (root / ".github" / "workflows" / "ci.yml").read_text(encoding="utf-8")

        self.assertIn("python -m compileall src tests", workflow)
        self.assertNotIn("python -m compileall ai app crawler", workflow)


if __name__ == "__main__":
    unittest.main()
