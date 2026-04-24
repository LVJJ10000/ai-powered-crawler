# Contributing

Thanks for considering a contribution.

## Development Setup

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

## Tests

Run the test suite before opening a pull request:

```bash
python -m unittest discover -s tests -v
```

## Pull Requests

- Keep changes focused on one problem.
- Add or update tests for behavior changes.
- Do not commit secrets, generated crawl outputs, caches, or local tool settings.
- Document user-facing changes in `README.md`.

## Security

Do not open public issues for credentials, vulnerabilities, or private crawl targets. Follow `SECURITY.md`.
