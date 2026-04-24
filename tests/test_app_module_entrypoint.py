import runpy
import unittest
from unittest.mock import patch


class TestAppModuleEntrypoint(unittest.TestCase):
    def test_python_m_app_invokes_cli_main(self):
        with patch("app.cli.main") as mock_main:
            runpy.run_module("app", run_name="__main__")

        mock_main.assert_called_once_with()


if __name__ == "__main__":
    unittest.main()
