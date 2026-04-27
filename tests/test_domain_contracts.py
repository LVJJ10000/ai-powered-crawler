import unittest
from dataclasses import is_dataclass

from domain.analysis_entities import ExtractType, PageType
from domain.crawl_entities import CrawlRequest, LinkCandidate, LinkSelection
from domain.extraction_entities import CrawlPlan, ExtractionRecord, FieldDefinition
from domain.models import RunConfig, SelectedLinksResult, XPathCandidate
from models.schemas import CrawlConfig, FieldXPath, PageData


class TestDomainContracts(unittest.TestCase):
    def test_legacy_runtime_models_alias_new_domain_entities(self):
        self.assertIs(RunConfig, CrawlRequest)
        self.assertIs(XPathCandidate, LinkCandidate)
        self.assertIs(SelectedLinksResult, LinkSelection)
        self.assertIs(CrawlConfig, CrawlPlan)
        self.assertIs(FieldXPath, FieldDefinition)
        self.assertIs(PageData, ExtractionRecord)
        self.assertTrue(is_dataclass(CrawlRequest))

    def test_new_domain_entities_keep_existing_runtime_shape(self):
        plan = CrawlPlan(
            page_type=PageType.DETAIL,
            fields=[
                FieldDefinition(
                    name="title",
                    description="Title",
                    xpath="//h1",
                    confidence=0.9,
                    extract=ExtractType.TEXT,
                )
            ],
        )

        request = CrawlRequest(
            start_url="https://example.com/detail/1",
            output_path="out.json",
            max_pages=5,
            max_list_pages=2,
            use_playwright=False,
            depth=2,
        )

        self.assertEqual(PageType.DETAIL, plan.page_type)
        self.assertEqual("https://example.com/detail/1", request.start_url)


if __name__ == "__main__":
    unittest.main()
