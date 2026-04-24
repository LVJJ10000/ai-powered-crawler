import unittest
from unittest.mock import patch

from app import cli


class TestCliReleaseDefaults(unittest.TestCase):
    def test_build_run_config_requires_explicit_url_and_uses_safe_defaults(self):
        run_config = cli.build_run_config(
            [
                "https://example.com/list",
                "--output",
                "result.json",
                "--max-pages",
                "3",
                "--max-list-pages",
                "2",
            ]
        )

        self.assertEqual("https://example.com/list", run_config.start_url)
        self.assertEqual("result.json", run_config.output_path)
        self.assertEqual(3, run_config.max_pages)
        self.assertEqual(2, run_config.max_list_pages)
        self.assertFalse(run_config.use_playwright)

    def test_build_run_config_enables_playwright_only_when_requested(self):
        run_config = cli.build_run_config(
            [
                "https://example.com/list",
                "--use-playwright",
            ]
        )

        self.assertTrue(run_config.use_playwright)

    def test_build_client_kwargs_omits_base_url_when_unset(self):
        with patch.object(cli.config, "API_KEY", "test-key"), patch.object(cli.config, "BASE_URL", None):
            self.assertEqual({"api_key": "test-key"}, cli.build_client_kwargs())

    def test_build_client_kwargs_includes_custom_base_url_when_set(self):
        with patch.object(cli.config, "API_KEY", "test-key"), patch.object(
            cli.config, "BASE_URL", "https://example.test/v1"
        ):
            self.assertEqual(
                {"api_key": "test-key", "base_url": "https://example.test/v1"},
                cli.build_client_kwargs(),
            )

    def test_main_help_does_not_require_api_key(self):
        with patch.object(cli.config, "API_KEY", None), patch("sys.argv", ["ai-powered-crawler", "-h"]):
            with self.assertRaises(SystemExit) as context:
                cli.main()

        self.assertEqual(0, context.exception.code)


if __name__ == "__main__":
    unittest.main()
