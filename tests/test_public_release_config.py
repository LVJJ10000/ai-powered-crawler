import importlib
import os
import unittest
from unittest.mock import patch


class TestPublicReleaseConfig(unittest.TestCase):
    def _reload_config_with_env(self, env: dict[str, str]):
        import config

        with patch.dict(os.environ, env, clear=True):
            reloaded = importlib.reload(config)
            api_key = reloaded.API_KEY
            base_url = reloaded.BASE_URL

        importlib.reload(config)
        return api_key, base_url

    def test_config_has_no_default_secret_or_internal_base_url(self):
        api_key, base_url = self._reload_config_with_env({})

        self.assertIsNone(api_key)
        self.assertIsNone(base_url)

    def test_config_prefers_openai_standard_environment_names(self):
        api_key, base_url = self._reload_config_with_env(
            {
                "OPENAI_API_KEY": "test-openai-key",
                "OPENAI_BASE_URL": "https://example.test/v1",
            }
        )

        self.assertEqual("test-openai-key", api_key)
        self.assertEqual("https://example.test/v1", base_url)


if __name__ == "__main__":
    unittest.main()
