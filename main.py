import os
import json
import asyncio
import logging
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional, Tuple
from urllib.parse import quote_plus

import requests
from dateutil import parser as dateparser
from dotenv import load_dotenv
from playwright.async_api import async_playwright, Browser, BrowserContext, Page

# Load environment variables from .env file for local development.
load_dotenv()


# -----------------------------
# Config & Constants
# -----------------------------
DEFAULT_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
)


def is_debug() -> bool:
    """Return True if DEBUG is enabled via env or .env (1/true/yes/on)."""
    return os.environ.get("DEBUG", "0").lower() in ("1", "true", "yes", "on")


# -----------------------------
# Logging
# -----------------------------
LOG_FORMAT = "%(levelname)s - %(asctime)s - %(message)s"
LOG_LEVEL = logging.DEBUG if is_debug() else logging.INFO
logging.basicConfig(level=LOG_LEVEL, format=LOG_FORMAT)
logger = logging.getLogger(__name__)


def load_config(path: str) -> List[dict]:
    """Load config.json which contains an array of jobs."""
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    if isinstance(data, list):
        return data
    raise ValueError("config.json must be an array of jobs.")


def resolve_max_pages(job: dict, default: int = 5) -> int:
    """Resolve max pages from job or environment variables."""
    if isinstance(job, dict) and job.get("max_pages") is not None:
        try:
            val = int(job["max_pages"])
            if val > 0:
                return val
        except (ValueError, TypeError):
            pass
    for key in ("NOTE_SEARCH_MAX_PAGES", "MAX_PAGES"):
        if key in os.environ:
            try:
                return int(os.environ[key])
            except (ValueError, TypeError):
                pass
    return default


# -----------------------------
# Playwright Helpers
# -----------------------------
async def new_browser() -> Tuple[Any, Browser, BrowserContext, Page]:
    """Start a Chromium browser with production-ready arguments."""
    pw = await async_playwright().start()
    launch_args = [
        '--no-sandbox',
        '--disable-setuid-sandbox',
        '--disable-dev-shm-usage',
        '--disable-gpu',
        '--no-first-run',
        '--no-zygote',
        '--single-process',
    ]
    browser = await pw.chromium.launch(headless=True, args=launch_args)
    context = await browser.new_context(user_agent=DEFAULT_UA)
    page = await context.new_page()
    return pw, browser, context, page


async def fetch_json_with_retries(page: Page, url: str, max_attempts: int = 3) -> Any:
    """
    Fetch JSON using Playwright's built-in request context.
    Includes retries with exponential backoff.
    """
    for attempt in range(max_attempts):
        try:
            response = await page.request.get(url, headers={"Accept": "application/json"})
            if not response.ok:
                raise Exception(f"HTTP status {response.status}")
            
            data = await response.json()

            if is_debug():
                os.makedirs("debug", exist_ok=True)
                with open(f"debug/success_{datetime.now().timestamp()}.json", "w") as f:
                    json.dump(data, f, indent=2)

            return data

        except (json.JSONDecodeError, Exception) as e:
            logger.warning(f"Attempt {attempt + 1}/{max_attempts} failed for {url}. Error: {e}")
            if attempt + 1 == max_attempts:
                logger.error(f"All attempts failed for {url}. Giving up.")
                raise
            
            wait_time = 2 ** (attempt + 1)
            logger.info(f"Retrying in {wait_time} seconds...")
            await asyncio.sleep(wait_time)


# -----------------------------
# Substack API Logic
# -----------------------------
NOTE_SEARCH_ENDPOINT = "https://substack.com/api/v1/note/search"

async def fetch_notes_all_pages(page: Page, keyword: str, max_pages: int = 5) -> List[dict]:
    """Fetch up to max_pages of results, handling pagination correctly."""
    aggregated_items: List[dict] = []
    seen_ids = set()
    cursor = None
    
    for page_num in range(max_pages):
        query_params = {"query": keyword}
        if cursor:
            query_params["cursor"] = cursor

        encoded_params = '&'.join([f"{key}={quote_plus(str(value))}" for key, value in query_params.items()])
        url = f"{NOTE_SEARCH_ENDPOINT}?{encoded_params}"
        
        logger.info(f"Fetching page {page_num + 1} for keyword '{keyword}'...")
        data = await fetch_json_with_retries(page, url)

        if not isinstance(data, dict) or not isinstance(data.get("items"), list):
            logger.warning("API response was invalid. Stopping pagination.")
            break

        new_items = 0
        for item in data["items"]:
            item_id = item.get("comment", {}).get("id")
            if item_id and item_id not in seen_ids:
                seen_ids.add(item_id)
                aggregated_items.append(item)
                new_items += 1
        
        logger.debug(f"Page {page_num + 1}: Fetched {len(data['items'])} items, added {new_items} new.")

        cursor = data.get("nextCursor")
        if not cursor:
            logger.info("No more pages found. Ending search.")
            break
            
    return aggregated_items


def parse_dt(value: Any) -> Optional[datetime]:
    if not value: return None
    try:
        if isinstance(value, (int, float)):
            ts = value / 1000 if value > 1_000_000_000_000 else value
            return datetime.fromtimestamp(ts, tz=timezone.utc)
        if isinstance(value, str):
            dt = dateparser.parse(value)
            return dt.astimezone(timezone.utc) if dt.tzinfo else dt.replace(tzinfo=timezone.utc)
    except (ValueError, TypeError): return None
    return None


def normalize_note(item: dict) -> Optional[dict]:
    """Normalize the raw API item into our clean, final format."""
    c = item.get("comment")
    if not isinstance(c, dict): return None

    text = c.get("body")
    if not (isinstance(text, str) and text.strip()): return None

    author_handle = c.get("handle")
    author_name = (item.get("context", {}).get("users", [{}])[0].get("name"))
    created_at = parse_dt(c.get("date"))
    note_id = c.get("id")

    try:
        likes = int(c.get("reaction_count", 0))
        comments = int(c.get("children_count", 0))
        restacks = int(c.get("restacks", 0))
    except (ValueError, TypeError):
        likes, comments, restacks = 0, 0, 0

    return {
        "id": note_id, "type": "comment", "text": text,
        "author_handle": author_handle, "author_name": author_name,
        "created_at": created_at.isoformat() if created_at else None,
        "likes": likes, "comments_count": comments, "restacks": restacks,
        "engagement": likes + comments + restacks,
        "url": f"https://substack.com/note/{note_id}" if note_id else None,
        "raw": item if is_debug() else None,
    }


def filter_and_sort_notes(
    notes: List[dict], *, author_handle: Optional[str], days_limit: Optional[int]
) -> List[dict]:
    
    filtered = notes
    
    if author_handle:
        handle = author_handle.lstrip("@").lower()
        filtered = [n for n in filtered if n.get("author_handle", "").lower() == handle]

    if days_limit and days_limit > 0:
        threshold = datetime.now(timezone.utc) - timedelta(days=days_limit)
        filtered = [n for n in filtered if (dt := parse_dt(n.get("created_at"))) and dt >= threshold]

    filtered.sort(
        key=lambda n: (
            parse_dt(n.get("created_at")) or datetime.min.replace(tzinfo=timezone.utc),
            n.get("engagement", 0),
        ),
        reverse=True,
    )
    return filtered


async def process_job(page: Page, job: dict) -> Dict[str, Any]:
    keyword = job.get("keyword")
    author = job.get("author")
    days_limit = job.get("days_limit")

    if not keyword:
        logger.error(f"Job skipped: 'keyword' is required.")
        return {"job": job, "notes": [], "error": "keyword is required"}

    logger.info(f"Processing job: keyword='{keyword}', author='{author or 'any'}'")
    max_pages = resolve_max_pages(job)
    
    raw_items = await fetch_notes_all_pages(page, keyword, max_pages=max_pages)
    normalized_notes = [n for n in (normalize_note(it) for it in raw_items) if n]
    
    final_notes = filter_and_sort_notes(
        normalized_notes, author_handle=author, days_limit=days_limit
    )
    
    logger.info(f"Job finished: Found {len(final_notes)} notes for keyword '{keyword}'.")
    return {"job": job, "notes": final_notes}


# -----------------------------
# Main Execution Logic
# -----------------------------
async def run_scraper(jobs: List[dict]) -> Dict[str, Any]:
    pw, browser, context, page = None, None, None, None
    all_results = []
    try:
        pw, browser, context, page = await new_browser()
        for i, job in enumerate(jobs):
            try:
                result = await process_job(page, job)
                all_results.append(result)
            except Exception as e:
                error_name = e.__class__.__name__
                if "TargetClosedError" in error_name or "BrowserDisconnectedError" in error_name:
                    logger.error(f"Fatal browser error during job {i+1}: {e}. Attempting to restart and retry.")
                    if page: await page.close()
                    if context: await context.close()
                    if browser: await browser.close()
                    if pw: await pw.stop()
                    try:
                        pw, browser, context, page = await new_browser()
                        logger.info("Browser restarted. Retrying failed job...")
                        result = await process_job(page, job)
                        all_results.append(result)
                    except Exception as e2:
                        logger.exception(f"Retry failed after browser restart: {e2}")
                        all_results.append({"job": job, "notes": [], "error": str(e2)})
                else:
                    logger.exception(f"Unhandled error in job {i+1}: {e}")
                    all_results.append({"job": job, "notes": [], "error": str(e)})
    finally:
        if page: await page.close()
        if context: await context.close()
        if browser: await browser.close()
        if pw: await pw.stop()
    return {"results": all_results}


def post_webhook(payload: dict) -> Tuple[bool, Optional[str]]:
    url = os.environ.get("WEBHOOK_URL")
    if not url:
        logger.error("WEBHOOK_URL not set.")
        return False, "WEBHOOK_URL not set"
    logger.info(f"Sending results to webhook: {url}")
    try:
        r = requests.post(url, json=payload, timeout=30)
        r.raise_for_status()
        logger.info(f"Webhook call successful (Status: {r.status_code}).")
        return True, None
    except requests.RequestException as e:
        logger.exception(f"Webhook call failed: {e}")
        return False, str(e)


def lambda_handler(event: Optional[dict], context: Any) -> dict:
    """
    AWS Lambda entry point.
    - If invoked with a payload containing a 'jobs' key, it runs those jobs.
    - Otherwise, it falls back to running the jobs defined in config.json.
    """
    jobs = []
    # Method 1: Check for jobs in the invocation event first.
    if event and isinstance(event.get('jobs'), list):
        logger.info(f"Received {len(event['jobs'])} jobs from invocation event.")
        jobs = event['jobs']
    # Method 2: Fallback to the local config.json file.
    else:
        config_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "config.json")
        if not os.path.exists(config_path):
            logger.critical(f"Configuration file not found at {config_path}")
            return {"ok": False, "error": "config.json not found"}
        try:
            logger.info("No jobs in event payload, loading from local config.json.")
            jobs = load_config(config_path)
        except Exception as e:
            logger.critical(f"Failed to load or parse config.json: {e}", exc_info=True)
            return {"ok": False, "error": f"Failed to load config.json: {e}"}

    if not os.environ.get("WEBHOOK_URL"):
        logger.critical("WEBHOOK_URL is not set. Aborting.")
        return {"ok": False, "error": "WEBHOOK_URL environment variable is not set"}

    results = asyncio.run(run_scraper(jobs))
    ok, err = post_webhook(results)
    
    return {
        "ok": ok, 
        "error": err, 
        "counts": [len(r.get("notes", [])) for r in results.get("results", [])]
    }


def _run_main() -> int:
    logger.info("Starting local execution...")
    try:
        payload = lambda_handler({}, None)
        logger.info(f"Local run finished. Payload: {json.dumps(payload, indent=2)}")
        return 0 if payload.get("ok") else 1
    except Exception as e:
        logger.exception(f"An unhandled error occurred: {e}")
        return 2


if __name__ == "__main__":
    raise SystemExit(_run_main())