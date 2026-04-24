import pathlib
import unittest

import app.cli
import config


class TestSrcLayoutImports(unittest.TestCase):
    def test_runtime_modules_resolve_from_src_tree(self):
        app_cli_path = pathlib.Path(app.cli.__file__).resolve()
        config_path = pathlib.Path(config.__file__).resolve()

        self.assertIn("src", app_cli_path.parts)
        self.assertIn("src", config_path.parts)


if __name__ == "__main__":
    unittest.main()
