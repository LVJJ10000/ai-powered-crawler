import unittest
from unittest.mock import patch

from app import cli
from application.dto.crawl_outcomes import CrawlOutcome
from domain.analysis_entities import PageType
from domain.errors import InvalidStartPageError, MissingApiKeyError
from domain.extraction_entities import CrawlPlan
from models.schemas import PageData


class TestInterfaceBootstrap(unittest.IsolatedAsyncioTestCase):
    async def test_cli_run_builds_request_and_executes_real_bootstrapped_use_case(self):
        requests = []

        async def fake_execute(self, request):
            requests.append(request)
            return CrawlOutcome()

        with patch("interfaces.bootstrap.container._BootstrappedCrawlWebsite.execute", new=fake_execute):
            await cli.run(["https://example.com/list"])

        self.assertEqual("https://example.com/list", requests[0].start_url)

    async def test_cli_run_writes_export_and_prints_completion_message(self):
        async def fake_execute(self, request):
            return CrawlOutcome(
                records=[PageData(url="https://example.com/detail/1", data={"title": "Example"})],
                export_plan=CrawlPlan(page_type=PageType.DETAIL, fields=[]),
            )

        with patch("interfaces.bootstrap.container._BootstrappedCrawlWebsite.execute", new=fake_execute), patch(
            "infrastructure.storage.json_output_writer.JsonOutputWriter.write",
            return_value={},
        ) as write_mock, patch("builtins.print") as print_mock:
            await cli.run(["https://example.com/detail/1", "--output", "result.json"])

        write_mock.assert_called_once()
        print_mock.assert_any_call("\nDone!  1 detail records  ->  result.json")

    async def test_cli_run_translates_invalid_list_start_page_to_terminal_exit(self):
        async def fake_execute(self, request):
            raise InvalidStartPageError.missing_link_candidates()

        with patch("interfaces.bootstrap.container._BootstrappedCrawlWebsite.execute", new=fake_execute), patch(
            "builtins.print"
        ) as print_mock:
            with self.assertRaises(SystemExit) as context:
                await cli.run(["https://example.com/list"])

        self.assertEqual(1, context.exception.code)
        print_mock.assert_any_call("\nNo list-link XPath candidates found. Exiting.")

    async def test_cli_run_translates_invalid_detail_start_page_to_terminal_exit(self):
        async def fake_execute(self, request):
            raise InvalidStartPageError.missing_detail_fields()

        with patch("interfaces.bootstrap.container._BootstrappedCrawlWebsite.execute", new=fake_execute), patch(
            "builtins.print"
        ) as print_mock:
            with self.assertRaises(SystemExit) as context:
                await cli.run(["https://example.com/detail/1"])

        self.assertEqual(1, context.exception.code)
        print_mock.assert_any_call("\nNo detail fields found. Exiting.")

    async def test_cli_run_translates_missing_api_key_to_terminal_exit(self):
        async def fake_execute(self, request):
            raise MissingApiKeyError()

        with patch("interfaces.bootstrap.container._BootstrappedCrawlWebsite.execute", new=fake_execute), patch(
            "builtins.print"
        ) as print_mock:
            with self.assertRaises(SystemExit) as context:
                await cli.run(["https://example.com/list"])

        self.assertEqual(1, context.exception.code)
        print_mock.assert_any_call("Error: OPENAI_API_KEY is not set")


if __name__ == "__main__":
    unittest.main()
