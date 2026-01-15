"""
Search providers for web research.

Implements DuckDuckGo HTML scraping with fallback chain.
No API keys or paid services required.
"""

import logging
import re
import time
from abc import ABC, abstractmethod
from typing import Dict, List

import requests  # type: ignore
from bs4 import BeautifulSoup

from spectral.research.knowledge_pack import SearchResult

logger = logging.getLogger(__name__)


class BaseSearchProvider(ABC):
    """Abstract base class for search providers."""

    def __init__(self):
        """Initialize search provider."""
        self.last_request_time: Dict[str, float] = {}
        self.cooldown_seconds = 1.5

    @abstractmethod
    def search(self, query: str, max_results: int = 5) -> List[SearchResult]:
        """
        Search for query and return results.

        Args:
            query: Search query
            max_results: Maximum results to return

        Returns:
            List of SearchResult objects
        """
        pass

    def rate_limit(self, domain: str = "default") -> None:
        """
        Enforce rate limiting per domain.

        Args:
            domain: Domain to rate limit
        """
        if domain in self.last_request_time:
            elapsed = time.time() - self.last_request_time[domain]
            if elapsed < self.cooldown_seconds:
                sleep_time = self.cooldown_seconds - elapsed
                logger.debug(f"Rate limiting: sleeping {sleep_time:.2f}s for {domain}")
                time.sleep(sleep_time)

        self.last_request_time[domain] = time.time()

    def get_headers(self) -> Dict[str, str]:
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


class DuckDuckGoHtmlProvider(BaseSearchProvider):
    """
    Primary search provider using DuckDuckGo HTML scraping.

    Scrapes DuckDuckGo HTML search results without using their API.
    """

    def __init__(self):
        """Initialize DuckDuckGo HTML provider."""
        super().__init__()
        self.base_url = "https://html.duckduckgo.com/html/"

    def search(self, query: str, max_results: int = 5) -> List[SearchResult]:
        """
        Search DuckDuckGo and return results.

        Args:
            query: Search query
            max_results: Maximum results to return (max 5)

        Returns:
            List of SearchResult objects
        """
        max_results = min(max_results, 5)
        logger.info(f"Searching DuckDuckGo HTML: {query}")

        self.rate_limit("duckduckgo.com")

        try:
            response = requests.post(
                self.base_url,
                data={"q": query},
                headers=self.get_headers(),
                timeout=10,
            )

            if response.status_code == 403 or response.status_code == 429:
                logger.warning(f"DuckDuckGo returned {response.status_code}, may be blocked")
                return []

            response.raise_for_status()

            soup = BeautifulSoup(response.text, "html.parser")
            results = self._parse_results(soup, max_results)

            logger.info(f"Found {len(results)} results from DuckDuckGo HTML")
            return results

        except requests.Timeout:
            logger.warning("DuckDuckGo search timed out")
            return []
        except requests.RequestException as e:
            logger.error(f"DuckDuckGo search failed: {e}")
            return []
        except Exception as e:
            logger.error(f"Unexpected error in DuckDuckGo search: {e}")
            return []

    def _parse_results(self, soup: BeautifulSoup, max_results: int) -> List[SearchResult]:
        """
        Parse search results from HTML.

        Args:
            soup: BeautifulSoup object
            max_results: Maximum results to extract

        Returns:
            List of SearchResult objects
        """
        results = []
        result_divs = soup.find_all("div", class_=re.compile(r"result"))

        for rank, div in enumerate(result_divs[:max_results], start=1):
            try:
                title_link = div.find("a", class_=re.compile(r"result__a"))
                if not title_link:
                    continue

                title = title_link.get_text(strip=True)
                url = title_link.get("href", "")

                snippet_tag = div.find("a", class_=re.compile(r"result__snippet"))
                snippet = snippet_tag.get_text(strip=True) if snippet_tag else ""

                if title and url:
                    results.append(
                        SearchResult(
                            title=title,
                            url=url,
                            snippet=snippet,
                            rank=rank,
                        )
                    )
            except Exception as e:
                logger.debug(f"Failed to parse result {rank}: {e}")
                continue

        return results


class DuckDuckGoLiteProvider(BaseSearchProvider):
    """
    Fallback search provider using DuckDuckGo Lite.

    Uses the simpler lite.duckduckgo.com endpoint when main provider fails.
    """

    def __init__(self):
        """Initialize DuckDuckGo Lite provider."""
        super().__init__()
        self.base_url = "https://lite.duckduckgo.com/lite/"

    def search(self, query: str, max_results: int = 5) -> List[SearchResult]:
        """
        Search DuckDuckGo Lite and return results.

        Args:
            query: Search query
            max_results: Maximum results to return (max 5)

        Returns:
            List of SearchResult objects
        """
        max_results = min(max_results, 5)
        logger.info(f"Searching DuckDuckGo Lite: {query}")

        self.rate_limit("lite.duckduckgo.com")

        try:
            response = requests.post(
                self.base_url,
                data={"q": query},
                headers=self.get_headers(),
                timeout=10,
            )

            if response.status_code == 403 or response.status_code == 429:
                logger.warning(f"DuckDuckGo Lite returned {response.status_code}")
                return []

            response.raise_for_status()

            soup = BeautifulSoup(response.text, "html.parser")
            results = self._parse_results(soup, max_results)

            logger.info(f"Found {len(results)} results from DuckDuckGo Lite")
            return results

        except requests.Timeout:
            logger.warning("DuckDuckGo Lite search timed out")
            return []
        except requests.RequestException as e:
            logger.error(f"DuckDuckGo Lite search failed: {e}")
            return []
        except Exception as e:
            logger.error(f"Unexpected error in DuckDuckGo Lite search: {e}")
            return []

    def _parse_results(self, soup: BeautifulSoup, max_results: int) -> List[SearchResult]:
        """
        Parse search results from Lite HTML.

        Args:
            soup: BeautifulSoup object
            max_results: Maximum results to extract

        Returns:
            List of SearchResult objects
        """
        results = []
        result_rows = soup.find_all("tr")

        rank = 0
        for row in result_rows:
            if rank >= max_results:
                break

            try:
                links = row.find_all("a", class_="result-link")
                if not links:
                    continue

                link = links[0]
                title = link.get_text(strip=True)
                url = link.get("href", "")

                snippet_tag = row.find("td", class_="result-snippet")
                snippet = snippet_tag.get_text(strip=True) if snippet_tag else ""

                if title and url and url.startswith("http"):
                    rank += 1
                    results.append(
                        SearchResult(
                            title=title,
                            url=url,
                            snippet=snippet,
                            rank=rank,
                        )
                    )
            except Exception as e:
                logger.debug(f"Failed to parse lite result: {e}")
                continue

        return results


class SearchProviderChain:
    """
    Chain of search providers with automatic fallback.

    Tries providers in order until one succeeds.
    """

    def __init__(self):
        """Initialize provider chain."""
        self.providers = [
            DuckDuckGoHtmlProvider(),
            DuckDuckGoLiteProvider(),
        ]
        logger.info("Initialized search provider chain with 2 providers")

    def search(self, query: str, max_results: int = 5) -> List[SearchResult]:
        """
        Search using provider chain with fallback.

        Args:
            query: Search query
            max_results: Maximum results to return

        Returns:
            List of SearchResult objects
        """
        for i, provider in enumerate(self.providers, start=1):
            provider_name = provider.__class__.__name__
            logger.debug(f"Trying provider {i}/{len(self.providers)}: {provider_name}")

            results = provider.search(query, max_results)

            if results:
                logger.info(f"Search succeeded with {provider_name}")
                return results  # type: ignore[no-any-return]

            logger.warning(f"{provider_name} returned no results, trying next provider")

        logger.error("All search providers failed")
        return []
