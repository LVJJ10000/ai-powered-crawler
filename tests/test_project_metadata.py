import pathlib
import tomllib
import unittest


class TestProjectMetadata(unittest.TestCase):
    def setUp(self):
        self.root = pathlib.Path(__file__).resolve().parents[1]
        with (self.root / "pyproject.toml").open("rb") as pyproject_file:
            self.pyproject = tomllib.load(pyproject_file)

    def test_package_metadata_uses_normalized_project_name(self):
        project = self.pyproject["project"]

        self.assertEqual("ai-powered-crawler", project["name"])
        self.assertEqual("Experimental AI-powered adaptive crawler", project["description"])
        self.assertEqual("AI-Powered-Crawler contributors", project["authors"][0]["name"])

    def test_console_script_uses_normalized_project_name(self):
        scripts = self.pyproject["project"]["scripts"]
        legacy_script_name = "ai-" + "crwal"

        self.assertEqual("app.cli:main", scripts["ai-powered-crawler"])
        self.assertNotIn(legacy_script_name, scripts)

    def test_package_metadata_uses_src_layout(self):
        setuptools_config = self.pyproject["tool"]["setuptools"]

        self.assertEqual({"": "src"}, setuptools_config["package-dir"])
        self.assertEqual(["config"], setuptools_config["py-modules"])
        self.assertEqual(["src"], setuptools_config["packages"]["find"]["where"])

    def test_readme_uses_public_project_name(self):
        readme = (self.root / "README.md").read_text(encoding="utf-8")

        self.assertTrue(readme.startswith("# AI-Powered-Crawler\n"))
        self.assertIn("AI-Powered-Crawler is an experimental adaptive crawler.", readme)

    def test_readme_uses_supported_runtime_commands(self):
        readme = (self.root / "README.md").read_text(encoding="utf-8")

        self.assertIn("ai-powered-crawler", readme)
        self.assertIn("python -m app", readme)
        self.assertNotIn("python main.py", readme)


if __name__ == "__main__":
    unittest.main()
