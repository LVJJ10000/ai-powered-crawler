import unittest

from application.services.extraction_coordinator import ExtractionCoordinator
from models.schemas import CrawlConfig, ExtractType, FieldXPath, PageData, PageType


class _FakeBatchExtractor:
    def __init__(self):
        self.calls = []

    def extract_batch(self, batch, crawl_plan, health_tracker=None, client=None, label=""):
        self.calls.append(
            {
                "batch": batch,
                "crawl_plan": crawl_plan,
                "health_tracker": health_tracker,
                "client": client,
                "label": label,
            }
        )
        return [PageData(url=batch[0][0], data={"title": "ok"})], crawl_plan


class _TrackingBatchExtractor:
    def __init__(self):
        self.health_trackers = []

    def extract_batch(self, batch, crawl_plan, health_tracker=None, client=None, label=""):
        self.health_trackers.append(health_tracker)
        return [], crawl_plan


class TestExtractionCoordinator(unittest.TestCase):
    def test_extract_batch_delegates_to_batch_extractor(self):
        crawl_plan = CrawlConfig(page_type=PageType.DETAIL, fields=[], pagination_xpath=None)
        batch_extractor = _FakeBatchExtractor()
        coordinator = ExtractionCoordinator(batch_extractor=batch_extractor)

        records, export_plan = coordinator.extract_batch(
            [("https://example.com/detail/1", "<html>one</html>")],
            crawl_plan,
            client="client",
            label="detail:example.com",
        )

        self.assertEqual(1, len(records))
        self.assertIs(export_plan, crawl_plan)
        self.assertEqual(
            [
                {
                    "batch": [("https://example.com/detail/1", "<html>one</html>")],
                    "crawl_plan": crawl_plan,
                    "health_tracker": batch_extractor.calls[0]["health_tracker"],
                    "client": "client",
                    "label": "detail:example.com",
                }
            ],
            batch_extractor.calls,
        )

    def test_extract_batch_reuses_session_health_tracker_across_batches(self):
        crawl_plan = CrawlConfig(
            page_type=PageType.DETAIL,
            fields=[
                FieldXPath(
                    name="title",
                    description="Title",
                    xpath="//h1",
                    confidence=0.9,
                    extract=ExtractType.TEXT,
                )
            ],
            pagination_xpath=None,
        )
        batch_extractor = _TrackingBatchExtractor()
        coordinator = ExtractionCoordinator(batch_extractor=batch_extractor)

        coordinator.extract_batch(
            [("https://example.com/detail/1", "<html>one</html>")],
            crawl_plan,
            session_key="detail:example.com",
        )
        coordinator.extract_batch(
            [("https://example.com/detail/2", "<html>two</html>")],
            crawl_plan,
            session_key="detail:example.com",
        )

        self.assertIsNotNone(batch_extractor.health_trackers[0])
        self.assertIs(
            batch_extractor.health_trackers[0],
            batch_extractor.health_trackers[1],
        )

    def test_extract_batch_scopes_health_tracker_by_session_key(self):
        crawl_plan = CrawlConfig(
            page_type=PageType.DETAIL,
            fields=[
                FieldXPath(
                    name="title",
                    description="Title",
                    xpath="//h1",
                    confidence=0.9,
                    extract=ExtractType.TEXT,
                )
            ],
            pagination_xpath=None,
        )
        batch_extractor = _TrackingBatchExtractor()
        coordinator = ExtractionCoordinator(batch_extractor=batch_extractor)

        coordinator.extract_batch(
            [("https://example.com/detail/1", "<html>one</html>")],
            crawl_plan,
            session_key="detail:example.com",
        )
        coordinator.extract_batch(
            [("https://other.example/detail/1", "<html>two</html>")],
            crawl_plan,
            session_key="detail:other.example",
        )

        self.assertIsNot(
            batch_extractor.health_trackers[0],
            batch_extractor.health_trackers[1],
        )

    def test_discover_child_urls_uses_record_data_and_html_links(self):
        crawl_plan = CrawlConfig(
            page_type=PageType.DETAIL,
            fields=[
                FieldXPath(
                    name="related_url",
                    description="Related page",
                    xpath="//a/@href",
                    confidence=0.9,
                    extract=ExtractType.ATTRIBUTE,
                    attribute_name="href",
                )
            ],
            pagination_xpath=None,
        )
        coordinator = ExtractionCoordinator()
        record = PageData(
            url="https://example.com/detail/1",
            data={"related_url": "/detail/2"},
        )

        urls = coordinator.discover_child_urls(
            record=record,
            crawl_plan=crawl_plan,
            page_html="""
                <html>
                    <body>
                        <a href="/detail/1">Self</a>
                        <a href="/detail/2">From field</a>
                        <a href="/detail/3">Sibling</a>
                        <a href="/other/4">Other</a>
                    </body>
                </html>
            """,
            page_url="https://example.com/detail/1",
            remaining_pages=5,
        )

        self.assertEqual(
            [
                "https://example.com/detail/2",
                "https://example.com/detail/3",
            ],
            urls,
        )
