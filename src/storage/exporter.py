"""
JSON Exporter - saves crawled detail data to JSON files.
"""

import json
from dataclasses import asdict, is_dataclass
from models.schemas import PageData, CrawlConfig


def _serialize_record(record: PageData) -> dict:
    model_dump = getattr(record, "model_dump", None)
    if callable(model_dump):
        return model_dump()

    if is_dataclass(record):
        return asdict(record)

    if hasattr(record, "__dict__"):
        return dict(record.__dict__)

    raise TypeError(f"Unsupported export record type: {type(record)!r}")


def export_json(
    data: list[PageData],
    crawl_config: CrawlConfig,
    source_url: str,
    output_path: str,
    detail_urls: list[str] | None = None,
):
    """Export detail page data to JSON."""
    fields_def = []
    for f in crawl_config.fields:
        fields_def.append({
            "name": f.name,
            "xpath": f.xpath,
            "description": f.description,
            "extract": f.extract.value,
            "confidence": f.confidence,
        })

    output = {
        "source_url": source_url,
        "page_type": crawl_config.page_type.value,
        "total_records": len(data),
        "fields_definition": fields_def,
        "pages": [_serialize_record(page) for page in data],
    }

    if detail_urls is not None:
        output["detail_urls"] = detail_urls

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(output, f, indent=2, ensure_ascii=False)

    print(f"Exported {len(data)} detail records to {output_path}")
