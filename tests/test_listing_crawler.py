import unittest

from application.dto.start_page_analysis import StartPageAnalysis
from domain.analysis_entities import PageType
from domain.crawl_entities import CrawlRequest, LinkCandidate
from domain.extraction_entities import CrawlPlan, ExtractionRecord
from models.schemas import PageData

from application.use_cases.crawl_listing import ListingCrawler


class _FakePaginator:
    def __init__(self):
        self.calls = []

    async def follow(self, start_html, start_url, pagination_xpath, pagination_type, max_list_pages):
        self.calls.append(
            {
                "start_html": start_html,
                "start_url": start_url,
                "pagination_xpath": pagination_xpath,
                "pagination_type": pagination_type,
                "max_list_pages": max_list_pages,
            }
        )
        return [
            ("https://example.com/list", "<html>page one</html>"),
            ("https://example.com/list?page=2", "<html>page two</html>"),
        ]


class _FakeDiscovery:
    def __init__(self):
        self.calls = []

    def select(self, candidates, list_pages, max_pages):
        self.calls.append(
            {
                "candidates": candidates,
                "list_pages": list_pages,
                "max_pages": max_pages,
            }
        )
        return type(
            "Selection",
            (),
            {
                "selected_urls": [
                    "https://example.com/detail/1",
                    "https://example.com/detail/2",
                ],
                "selected_xpaths": ["//main//a/@href"],
                "evaluations": [],
            },
        )()


class _FakeDetailCrawler:
    def __init__(self):
        self.process_calls = []

    async def process_depth_layer(self, urls, remaining_pages, crawl_plan_cache=None, prefetched_pages=None):
        self.process_calls.append(
            {
                "urls": urls,
                "remaining_pages": remaining_pages,
                "crawl_plan_cache": crawl_plan_cache,
                "prefetched_pages": prefetched_pages,
            }
        )
        return type(
            "DetailResult",
            (),
            {
                "records": [PageData(url=url, data={"title": url.rsplit("/", 1)[-1]}) for url in urls],
                "export_config": CrawlPlan(page_type=PageType.DETAIL, fields=[]),
            },
        )()


class TestListingCrawler(unittest.IsolatedAsyncioTestCase):
    async def test_discover_detail_urls_uses_pagination_and_candidate_selection(self):
        paginator = _FakePaginator()
        discovery = _FakeDiscovery()
        crawler = ListingCrawler(
            paginator=paginator,
            detail_url_discovery=discovery,
            detail_crawler=_FakeDetailCrawler(),
        )
        request = CrawlRequest(
            start_url="https://example.com/list",
            output_path="out.json",
            max_pages=10,
            max_list_pages=2,
        )
        analysis = StartPageAnalysis(
            page_type=PageType.LIST,
            crawl_plan=CrawlPlan(page_type=PageType.LIST, fields=[]),
            link_candidates=[LinkCandidate(xpath="//main//a/@href", confidence=0.8)],
        )

        result = await crawler.discover_detail_urls(request, "<html>start</html>", analysis)

        self.assertEqual(
            [
                "https://example.com/detail/1",
                "https://example.com/detail/2",
            ],
            result.detail_urls,
        )
        self.assertEqual(["//main//a/@href"], result.selected_xpaths)
        self.assertEqual(1, len(paginator.calls))
        self.assertEqual(1, len(discovery.calls))

    async def test_run_delegates_selected_urls_to_detail_crawler(self):
        detail_crawler = _FakeDetailCrawler()
        crawler = ListingCrawler(
            paginator=_FakePaginator(),
            detail_url_discovery=_FakeDiscovery(),
            detail_crawler=detail_crawler,
        )
        request = CrawlRequest(
            start_url="https://example.com/list",
            output_path="out.json",
            max_pages=2,
            max_list_pages=2,
        )
        analysis = StartPageAnalysis(
            page_type=PageType.LIST,
            crawl_plan=CrawlPlan(page_type=PageType.LIST, fields=[]),
            link_candidates=[LinkCandidate(xpath="//main//a/@href", confidence=0.8)],
        )

        records, export_plan = await crawler.run(request, "<html>start</html>", analysis)

        self.assertEqual(
            ["https://example.com/detail/1", "https://example.com/detail/2"],
            [record.url for record in records],
        )
        self.assertEqual(
            [
                {
                    "urls": [
                        "https://example.com/detail/1",
                        "https://example.com/detail/2",
                    ],
                    "remaining_pages": 2,
                    "crawl_plan_cache": None,
                    "prefetched_pages": None,
                }
            ],
            detail_crawler.process_calls,
        )
        self.assertEqual(PageType.DETAIL, export_plan.page_type)


if __name__ == "__main__":
    unittest.main()
