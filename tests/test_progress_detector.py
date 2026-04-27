import unittest

from services.progress_detector import ProgressDetector


class TestProgressDetector(unittest.TestCase):
    def test_has_progress_when_same_text_but_link_targets_change(self):
        detector = ProgressDetector()
        previous = detector.capture_snapshot(
            "https://example.com/list",
            "<html><body><a href='/detail/1'>Read more</a></body></html>",
        )
        current = detector.capture_snapshot(
            "https://example.com/list",
            "<html><body><a href='/detail/2'>Read more</a></body></html>",
        )

        self.assertTrue(detector.has_progress(previous, current))

    def test_has_no_progress_for_identical_same_url_snapshot(self):
        detector = ProgressDetector()
        html = "<html><body><a href='/detail/1'>Read more</a></body></html>"

        previous = detector.capture_snapshot("https://example.com/list", html)
        current = detector.capture_snapshot("https://example.com/list", html)

        self.assertFalse(detector.has_progress(previous, current))


if __name__ == "__main__":
    unittest.main()
