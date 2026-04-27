from application.use_cases.crawl_website import START_PAGE_ANALYZED


class ConsoleRunReporter:
    def publish(self, event):
        if event.get("type") != START_PAGE_ANALYZED:
            return

        page_type = event.get("page_type", "unknown").upper()
        print(f"\nStart page classified as: {page_type}")
