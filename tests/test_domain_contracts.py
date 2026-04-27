import unittest
from dataclasses import is_dataclass

from domain.analysis_entities import ExtractType, PageType
from domain.crawl_entities import (
    CrawlRequest,
    LinkCandidate,
    LinkCandidateEvaluation,
    LinkSelection,
    PatternModel,
)
from domain.extraction_entities import CrawlPlan, ExtractionRecord, FieldDefinition
from domain.models import (
    PatternModel as LegacyPatternModel,
    RunConfig,
    SelectedLinksResult,
    XPathCandidate,
    XPathCandidateEvaluation,
)
from models.schemas import CrawlConfig, FieldXPath, PageData


class TestDomainContracts(unittest.TestCase):
    def test_legacy_runtime_models_alias_new_domain_entities(self):
        self.assertIs(RunConfig, CrawlRequest)
        self.assertIs(XPathCandidate, LinkCandidate)
        self.assertIs(XPathCandidateEvaluation, LinkCandidateEvaluation)
        self.assertIs(LegacyPatternModel, PatternModel)
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

    def test_crawl_request_aliases_remain_mutable_like_legacy_models(self):
        request = CrawlRequest(
            start_url="https://example.com/detail/1",
            output_path="out.json",
            max_pages=5,
            max_list_pages=2,
        )

        request.depth = 3

        self.assertEqual(3, request.depth)

    def test_extraction_aliases_do_not_add_extra_runtime_methods(self):
        record = PageData(url="https://example.com/detail/1", data={"title": "Example"})

        self.assertFalse(hasattr(record, "model_dump"))

    def test_link_selection_uses_explicit_evaluation_entities(self):
        selection = LinkSelection(
            evaluations=[
                LinkCandidateEvaluation(
                    candidate=LinkCandidate(xpath="//main//a/@href"),
                    urls=["https://example.com/detail/1"],
                    score=0.8,
                )
            ]
        )

        self.assertEqual("//main//a/@href", selection.evaluations[0].candidate.xpath)
        self.assertEqual(0.8, selection.evaluations[0].score)


if __name__ == "__main__":
    unittest.main()
