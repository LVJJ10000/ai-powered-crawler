import json
from dataclasses import asdict, is_dataclass

from models.schemas import CrawlConfig, PageData


def _serialize_record(record: PageData) -> dict:
    model_dump = getattr(record, "model_dump", None)
    if callable(model_dump):
        return model_dump()

    if is_dataclass(record):
        return asdict(record)

    if hasattr(record, "__dict__"):
        return dict(record.__dict__)

    raise TypeError(f"Unsupported export record type: {type(record)!r}")


class JsonOutputWriter:
    def write(
        self,
        data: list[PageData],
        crawl_config: CrawlConfig,
        source_url: str,
        output_path: str,
        detail_urls: list[str] | None = None,
    ):
        fields_def = []
        for field in crawl_config.fields:
            fields_def.append(
                {
                    "name": field.name,
                    "xpath": field.xpath,
                    "description": field.description,
                    "extract": field.extract.value,
                    "confidence": field.confidence,
                }
            )

        output = {
            "source_url": source_url,
            "page_type": crawl_config.page_type.value,
            "total_records": len(data),
            "fields_definition": fields_def,
            "pages": [_serialize_record(page) for page in data],
        }

        if detail_urls is not None:
            output["detail_urls"] = detail_urls

        with open(output_path, "w", encoding="utf-8") as handle:
            json.dump(output, handle, indent=2, ensure_ascii=False)

        print(f"Exported {len(data)} detail records to {output_path}")
        return output
