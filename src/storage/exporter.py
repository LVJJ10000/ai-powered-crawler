"""
JSON Exporter - saves crawled detail data to JSON files.
"""

from infrastructure.storage.json_output_writer import JsonOutputWriter


def export_json(
    data,
    crawl_config,
    source_url,
    output_path,
    detail_urls=None,
):
    return JsonOutputWriter().write(
        data=data,
        crawl_config=crawl_config,
        source_url=source_url,
        output_path=output_path,
        detail_urls=detail_urls,
    )
