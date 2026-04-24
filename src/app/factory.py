from pipelines.detail_pipeline import DetailPipeline
from pipelines.list_pipeline import ListPipeline
from services.extraction_service import ExtractionService
from services.link_xpath_service import LinkXPathService
from services.page_analysis_service import PageAnalysisService
from services.pagination_service import PaginationService
from services.pattern_learning_service import PatternLearningService


class ServiceFactory:
    @staticmethod
    def build(
        client,
        fetcher,
    ):
        analyzer_service = PageAnalysisService(client=client)
        extraction_service = ExtractionService()
        pattern_learning_service = PatternLearningService()
        link_xpath_service = LinkXPathService(pattern_learner=pattern_learning_service)
        pagination_service = PaginationService(fetcher=fetcher)

        list_pipeline = ListPipeline(
            fetcher=fetcher,
            analyzer_service=analyzer_service,
            extraction_service=extraction_service,
            pagination_service=pagination_service,
            link_xpath_service=link_xpath_service,
        )
        detail_pipeline = DetailPipeline(
            fetcher=fetcher,
            extraction_service=extraction_service,
            analyzer_service=analyzer_service,
        )
        return analyzer_service, list_pipeline, detail_pipeline

