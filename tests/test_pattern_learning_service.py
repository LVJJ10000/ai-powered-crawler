import unittest

from services.pattern_learning_service import PatternLearningService


class TestPatternLearningService(unittest.TestCase):
    def test_learn_builds_generalized_patterns(self):
        service = PatternLearningService()
        urls = [
            "https://news.example.com/article/2026-04-22/12345",
            "https://news.example.com/article/2026-04-23/67890",
            "https://news.example.com/article/2026-04-24/24680",
        ]

        model = service.learn(urls)

        self.assertTrue(model.pattern_counts)
        self.assertEqual(model.total_urls, 3)
        self.assertTrue(any("{id}" in key or "{date}" in key for key in model.pattern_counts.keys()))

    def test_evaluate_returns_coverage_and_top_support(self):
        service = PatternLearningService()
        urls = [
            "https://news.example.com/article/123",
            "https://news.example.com/article/456",
            "https://news.example.com/article/789",
        ]
        model = service.learn(urls)
        coverage, top_support = service.evaluate(urls, model)
        self.assertGreaterEqual(coverage, 0.0)
        self.assertGreaterEqual(top_support, 0.0)
        self.assertLessEqual(coverage, 1.0)
        self.assertLessEqual(top_support, 1.0)


if __name__ == "__main__":
    unittest.main()

