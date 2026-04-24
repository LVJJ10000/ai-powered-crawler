import os

# AI
API_KEY = os.getenv("OPENAI_API_KEY") or os.getenv("API_KEY")
MODEL = os.getenv("OPENAI_MODEL", "gpt-4o")
BASE_URL = os.getenv("OPENAI_BASE_URL") or os.getenv("BASE_URL")

# HTML Processing
MAX_HTML_SIZE = 30_000          # Max chars of cleaned HTML sent to AI

# Healing
MAX_HEAL_ATTEMPTS = 3           # Max heal retries per field before giving up
HEAL_CONSECUTIVE_THRESHOLD = 3  # Consecutive empty results to trigger heal
HEAL_RATE_THRESHOLD = 0.6       # Failure rate (in last 5 pages) to trigger heal
CASCADE_THRESHOLD = 0.5         # % of fields failing to trigger full re-detect

# Crawling
MAX_PAGES = 100                 # Default max pages to crawl
MAX_DEPTH = 3                   # Default max link crawl depth
REQUEST_TIMEOUT = 30            # Seconds
REQUEST_DELAY = 1.0             # Seconds between requests (politeness)

# User Agent
USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
