"""
URL fetching with requests and Playwright fallback.

Fetches web pages, extracts content, and falls back to Playwright for
JavaScript-heavy pages.
"""

import logging
import time
from typing import Dict, Optional
from urllib.parse import urlparse

import requests  # type: ignore

from spectral.research.extractor import ContentExtractor
from spectral.research.knowledge_pack import FetchResult

logger = logging.getLogger(__name__)

# Try to import Playwright, gracefully handle if not available
try:
    from playwright.sync_api import sync_playwright

    PLAYWRIGHT_AVAILABLE = True
except ImportError:
    PLAYWRIGHT_AVAILABLE = False
    logger.info("Playwright not available, JS-heavy pages may not work")


class RequestsFetcher:
    """Fetch web pages using requests library."""

    def __init__(self):
        """Initialize requests fetcher."""
        self.timeout = 15
        self.last_request_time: Dict[str, float] = {}
        self.cooldown_seconds = 1.0
        self.extractor = ContentExtractor()

    def fetch_url(self, url: str) -> FetchResult:
        """
        Fetch URL and extract content.

        Args:
            url: URL to fetch

        Returns:
            FetchResult with extracted content
        """
        logger.info(f"Fetching URL with requests: {url}")

        domain = urlparse(url).netloc
        self._rate_limit(domain)

        start_time = time.time()

        try:
            response = requests.get(
                url,
                headers=self._get_headers(),
                timeout=self.timeout,
                allow_redirects=True,
            )

            fetch_time = time.time() - start_time

            if response.status_code == 403 or response.status_code == 429:
                logger.warning(f"Got {response.status_code}, may need Playwright fallback")
                return FetchResult(
                    final_url=response.url,
                    status_code=response.status_code,
                    text="",
                    fetch_time=fetch_time,
                    fetcher_used="requests",
                )

            response.raise_for_status()

            html = response.text
            text = self.extractor.extract_main_content(html)
            title = self.extractor.extract_title(html)
            headings = self.extractor.extract_headings(html)
            code_blocks = self.extractor.extract_code_blocks(html)
            meta_description = self.extractor.extract_meta_description(html)

            if len(text.strip()) < 500:
                logger.info("Content too short, may be JS-heavy page")

            logger.info(f"Fetched {len(text)} chars in {fetch_time:.2f}s")

            return FetchResult(
                final_url=response.url,
                status_code=response.status_code,
                html=html,
                text=text,
                title=title,
                headings=headings,
                code_blocks=code_blocks,
                meta_description=meta_description,
                fetch_time=fetch_time,
                fetcher_used="requests",
            )

        except requests.Timeout:
            logger.warning(f"Request timed out: {url}")
            return FetchResult(
                final_url=url,
                status_code=0,
                text="",
                fetch_time=time.time() - start_time,
                fetcher_used="requests",
            )

        except requests.RequestException as e:
            logger.error(f"Request failed: {e}")
            return FetchResult(
                final_url=url,
                status_code=0,
                text="",
                fetch_time=time.time() - start_time,
                fetcher_used="requests",
            )

    def _rate_limit(self, domain: str) -> None:
        """Enforce per-domain rate limiting."""
        if domain in self.last_request_time:
            elapsed = time.time() - self.last_request_time[domain]
            if elapsed < self.cooldown_seconds:
                sleep_time = self.cooldown_seconds - elapsed
                time.sleep(sleep_time)

        self.last_request_time[domain] = time.time()

    def _get_headers(self) -> Dict[str, str]:
        """Get HTTP headers for requests."""
        return {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
            ),
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.9",
            "Accept-Encoding": "gzip, deflate",
            "DNT": "1",
            "Connection": "keep-alive",
            "Upgrade-Insecure-Requests": "1",
        }


class PlaywrightFetcher:
    """Fetch web pages using Playwright for JavaScript-heavy pages."""

    def __init__(self):
        """Initialize Playwright fetcher."""
        self.timeout = 20000
        self.extractor = ContentExtractor()

    def fetch_url(self, url: str) -> Optional[FetchResult]:
        """
        Fetch URL using Playwright.

        Args:
            url: URL to fetch

        Returns:
            FetchResult or None if Playwright not available
        """
        if not PLAYWRIGHT_AVAILABLE:
            logger.warning("Playwright not available, cannot fetch JS-heavy page")
            return None

        logger.info(f"Fetching URL with Playwright: {url}")
        start_time = time.time()

        try:
            with sync_playwright() as p:
                browser = p.chromium.launch(headless=True)
                page = browser.new_page()
                page.set_default_timeout(self.timeout)

                response = page.goto(url, wait_until="domcontentloaded")
                status_code = response.status if response else 0

                page.wait_for_timeout(2000)

                html = page.content()
                final_url = page.url

                browser.close()

            fetch_time = time.time() - start_time

            text = self.extractor.extract_main_content(html)
            title = self.extractor.extract_title(html)
            headings = self.extractor.extract_headings(html)
            code_blocks = self.extractor.extract_code_blocks(html)
            meta_description = self.extractor.extract_meta_description(html)

            logger.info(f"Playwright fetched {len(text)} chars in {fetch_time:.2f}s")

            return FetchResult(
                final_url=final_url,
                status_code=status_code,
                html=html,
                text=text,
                title=title,
                headings=headings,
                code_blocks=code_blocks,
                meta_description=meta_description,
                fetch_time=fetch_time,
                fetcher_used="playwright",
            )

        except Exception as e:
            logger.error(f"Playwright fetch failed: {e}")
            return None


class SmartFetcher:
    """
    Smart fetcher with automatic fallback.

    Tries requests first, falls back to Playwright if needed.
    """

    def __init__(self, enable_playwright: bool = True):
        """
        Initialize smart fetcher.

        Args:
            enable_playwright: Whether to enable Playwright fallback
        """
        self.requests_fetcher = RequestsFetcher()
        self.playwright_fetcher = PlaywrightFetcher() if enable_playwright else None
        self.enable_playwright = enable_playwright and PLAYWRIGHT_AVAILABLE

    def fetch_url(self, url: str) -> FetchResult:
        """
        Fetch URL with automatic fallback.

        Tries requests first, falls back to Playwright for:
        - 403/429 status codes
        - Content < 500 characters (likely JS-heavy)
        - Empty text

        Args:
            url: URL to fetch

        Returns:
            FetchResult with extracted content
        """
        result = self.requests_fetcher.fetch_url(url)

        needs_fallback = (
            result.status_code in [403, 429]
            or (result.status_code == 200 and len(result.text.strip()) < 500)
            or not result.text.strip()
        )

        if needs_fallback and self.enable_playwright and self.playwright_fetcher:
            logger.info("Requests fetch insufficient, trying Playwright fallback")
            playwright_result = self.playwright_fetcher.fetch_url(url)

            if playwright_result and len(playwright_result.text) > len(result.text):
                logger.info("Playwright fallback successful")
                return playwright_result
            else:
                logger.info("Playwright fallback did not improve result")

        return result
