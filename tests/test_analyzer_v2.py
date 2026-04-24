import json
import unittest

from ai.analyzer import analyze_list_fields, analyze_page_v2, detect_page_type
from models.schemas import DetailFieldAnalysisResult, ListFieldAnalysisResult, PageType


class _FakeMessage:
    def __init__(self, content: str):
        self.content = content


class _FakeChoice:
    def __init__(self, content: str):
        self.message = _FakeMessage(content)


class _FakeResponse:
    def __init__(self, content: str):
        self.choices = [_FakeChoice(content)]


class _FakeCompletions:
    def __init__(self, payloads: list[str]):
        self._payloads = payloads

    def create(self, **kwargs):
        if not self._payloads:
            raise RuntimeError("No fake payload left")
        return _FakeResponse(self._payloads.pop(0))


class _FakeChat:
    def __init__(self, payloads: list[str]):
        self.completions = _FakeCompletions(payloads)


class _FakeClient:
    def __init__(self, payloads: list[str]):
        self.chat = _FakeChat(payloads)


class TestAnalyzerV2(unittest.TestCase):
    def test_detect_page_type_returns_structured_result(self):
        payload = json.dumps(
            {
                "page_type": "list",
                "confidence": 0.92,
                "reason": "repeating result cards",
            }
        )
        client = _FakeClient([payload])
        annotated = '<html><body><div data-aid="e1">x</div></body></html>'

        result = detect_page_type(annotated, client)

        self.assertEqual(result.page_type, PageType.LIST)
        self.assertAlmostEqual(result.confidence, 0.92, places=2)
        self.assertIn("repeating", result.reason)

    def test_analyze_list_fields_keeps_only_valid_href_detail_urls(self):
        payload = json.dumps(
            {
                "page_type": "list",
                "container_aid": "c1",
                "primary_detail_link_xpath": "//ul[@data-aid='c1']//a/@href",
                "detail_link_xpath_candidates": [
                    {
                        "xpath": "//ul[@data-aid='c1']//a/@href",
                        "confidence": 0.95,
                        "reason": "main list links",
                    },
                    {
                        "xpath": "//div[@class='news-list']//a/@href",
                        "confidence": 0.85,
                        "reason": "usable real xpath",
                    },
                    {
                        "xpath": "",
                        "confidence": 0.5,
                    },
                ],
                "pagination": None,
            }
        )
        client = _FakeClient([payload])
        annotated = '<html><body><ul data-aid="c1"><li><a data-aid="u1" href="/a">a</a></li></ul></body></html>'

        result = analyze_list_fields(annotated, client)

        self.assertIsInstance(result, ListFieldAnalysisResult)
        self.assertEqual(result.container_aid, "c1")
        self.assertEqual(result.primary_detail_link_xpath, "//div[@class='news-list']//a/@href")
        self.assertEqual(len(result.detail_link_xpath_candidates), 1)
        self.assertEqual(result.detail_link_xpath_candidates[0].xpath, "//div[@class='news-list']//a/@href")

    def test_analyze_page_v2_routes_to_detail_job(self):
        detect_payload = json.dumps({"page_type": "detail", "confidence": 0.88, "reason": "single article"})
        detail_payload = json.dumps(
            {
                "page_type": "detail",
                "fields": [
                    {
                        "name": "title",
                        "aid": "t1",
                        "extract": "text",
                        "attribute_name": None,
                        "description": "article title",
                    }
                ],
            }
        )
        client = _FakeClient([detect_payload, detail_payload])
        annotated = '<html><body><h1 data-aid="t1">hello</h1></body></html>'

        page_result, analysis = analyze_page_v2(annotated, client)

        self.assertEqual(page_result.page_type, PageType.DETAIL)
        self.assertIsInstance(analysis, DetailFieldAnalysisResult)
        self.assertEqual(analysis.fields[0].name, "title")


if __name__ == "__main__":
    unittest.main()
