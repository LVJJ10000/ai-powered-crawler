# AI-Powered-Crawler

AI-Powered-Crawler is an experimental adaptive crawler. It fetches a start page, asks an OpenAI-compatible model to classify list/detail pages, learns XPath selectors, follows pagination, and exports extracted detail records to JSON.

## Features

- Classifies start pages as list or detail pages.
- Discovers detail links from list pages with XPath candidates.
- Extracts structured fields from detail pages.
- Supports HTTP fetching with optional Playwright rendering.
- Exports crawl results as JSON.
- Includes unit tests for analyzer, pagination, XPath, routing, and release configuration behavior.

## Requirements

- Python 3.11 or newer
- An OpenAI-compatible API key
- Chromium installed through Playwright when using `--use-playwright`

## Installation

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -e ".[dev]"
```

On Windows PowerShell:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -e ".[dev]"
```

Install Playwright's browser only if you need JavaScript rendering:

```bash
playwright install chromium
```

## Configuration

Set credentials through environment variables. Do not put secrets in source files.

```bash
export OPENAI_API_KEY="your-api-key"
export OPENAI_MODEL="gpt-4o"
```

For OpenAI-compatible providers:

```bash
export OPENAI_BASE_URL="https://your-provider.example/v1"
```

On Windows PowerShell:

```powershell
$env:OPENAI_API_KEY = "your-api-key"
$env:OPENAI_MODEL = "gpt-4o"
$env:OPENAI_BASE_URL = "https://your-provider.example/v1"
```

Legacy `API_KEY` and `BASE_URL` environment variables are still supported, but `OPENAI_API_KEY` and `OPENAI_BASE_URL` are preferred.

## Usage

```bash
ai-powered-crawler "https://example.com/articles" --output output.json --max-pages 20 --max-list-pages 5
```

Use the module entrypoint during development:

```bash
python -m app "https://example.com/articles" --output output.json --max-pages 20 --max-list-pages 5
```

Use Playwright for JavaScript-rendered pages:

```bash
python -m app "https://example.com/articles" --output output.json --use-playwright
```

## Testing

```bash
python -m unittest discover -s tests -v
```

## Responsible Crawling

Use this project only on websites you are allowed to crawl. Before running a crawl, review the target site's robots.txt, terms of service, and rate-limit expectations. Keep `REQUEST_DELAY` conservative in `config.py` for public websites.

## License

This project is licensed under the MIT License. See `LICENSE`.
