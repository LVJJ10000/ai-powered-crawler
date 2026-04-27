import unittest
from unittest.mock import patch

from app import cli


class _FakeUseCase:
    def __init__(self):
        self.requests = []

    async def execute(self, request):
        self.requests.append(request)
        return type("Result", (), {"records": [], "detail_urls": [], "export_plan": None})()


class _FakeContainer:
    def __init__(self, use_case):
        self.crawl_website = use_case
        self.output_writer = object()


class TestInterfaceBootstrap(unittest.IsolatedAsyncioTestCase):
    async def test_cli_run_builds_request_and_executes_bootstrapped_use_case(self):
        fake_use_case = _FakeUseCase()

        with patch("interfaces.cli.main.build_container", return_value=_FakeContainer(fake_use_case)):
            await cli.run(["https://example.com/list"])

        self.assertEqual("https://example.com/list", fake_use_case.requests[0].start_url)


if __name__ == "__main__":
    unittest.main()
