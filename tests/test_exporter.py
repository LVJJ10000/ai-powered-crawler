import json
import os
import tempfile
import unittest

from models.schemas import CrawlConfig, PageType
from storage.exporter import export_json


class TestExporter(unittest.TestCase):
    def test_export_json_omits_detail_urls_when_not_provided(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = os.path.join(tmpdir, "out.json")
            export_json(
                data=[],
                crawl_config=CrawlConfig(page_type=PageType.DETAIL, fields=[], pagination_xpath=None),
                source_url="https://example.com/detail/1",
                output_path=output_path,
            )

            with open(output_path, "r", encoding="utf-8") as handle:
                payload = json.load(handle)

        self.assertNotIn("detail_urls", payload)

    def test_export_json_includes_detail_urls_for_discovery_mode(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = os.path.join(tmpdir, "out.json")
            export_json(
                data=[],
                crawl_config=CrawlConfig(page_type=PageType.LIST, fields=[], pagination_xpath=None),
                source_url="https://example.com/list",
                output_path=output_path,
                detail_urls=[
                    "https://example.com/detail/1",
                    "https://example.com/detail/2",
                ],
            )

            with open(output_path, "r", encoding="utf-8") as handle:
                payload = json.load(handle)

        self.assertEqual(
            [
                "https://example.com/detail/1",
                "https://example.com/detail/2",
            ],
            payload["detail_urls"],
        )
        self.assertEqual([], payload["pages"])
        self.assertEqual(0, payload["total_records"])


if __name__ == "__main__":
    unittest.main()
