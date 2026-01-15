"""
Research orchestrator for web research pipeline.

Coordinates search → fetch → extract → synthesize workflow to build
knowledge packs from web research.
"""

import json
import logging
import sqlite3
from datetime import datetime, timedelta
from pathlib import Path
from typing import List, Optional

from spectral.llm_client import LLMClient
from spectral.research.fetcher import SmartFetcher
from spectral.research.knowledge_pack import FetchResult, KnowledgePack, SourceEvidence
from spectral.research.search_providers import SearchProviderChain

logger = logging.getLogger(__name__)


class ResearchOrchestrator:
    """
    Orchestrate web research to build knowledge packs.

    Workflow:
    1. Search for query (DuckDuckGo with fallback)
    2. Fetch top K results
    3. Extract content from each
    4. Synthesize knowledge pack via LLM
    5. Cache results
    """

    def __init__(
        self,
        cache_db_path: Optional[Path] = None,
        enable_playwright: bool = False,
        llm_client: Optional[LLMClient] = None,
    ):
        """
        Initialize research orchestrator.

        Args:
            cache_db_path: Path to cache database (defaults to ~/.spectral/research_cache.db)
            enable_playwright: Whether to enable Playwright for JS-heavy pages
            llm_client: LLM client for synthesis (creates default if None)
        """
        if cache_db_path is None:
            cache_dir = Path.home() / ".spectral" / "cache"
            cache_dir.mkdir(parents=True, exist_ok=True)
            cache_db_path = cache_dir / "research_cache.db"

        self.cache_db_path = cache_db_path
        self.search_provider = SearchProviderChain()
        self.fetcher = SmartFetcher(enable_playwright=enable_playwright)
        self.llm_client = llm_client or LLMClient()

        self._init_cache_db()

        logger.info(f"ResearchOrchestrator initialized with cache at {cache_db_path}")

    def _init_cache_db(self) -> None:
        """Initialize cache database schema."""
        conn = sqlite3.connect(str(self.cache_db_path))
        cursor = conn.cursor()

        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS web_cache (
                url TEXT PRIMARY KEY,
                final_url TEXT NOT NULL,
                status_code INTEGER NOT NULL,
                title TEXT,
                text TEXT NOT NULL,
                code_blocks TEXT,
                raw_html_path TEXT,
                meta_description TEXT,
                fetched_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                etag TEXT,
                last_modified TEXT,
                expires_at TIMESTAMP
            )
        """
        )

        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS search_cache (
                query TEXT PRIMARY KEY,
                provider TEXT NOT NULL,
                results_json TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                expires_at TIMESTAMP
            )
        """
        )

        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS knowledge_packs (
                id TEXT PRIMARY KEY,
                query TEXT NOT NULL,
                pack_json TEXT NOT NULL,
                sources_json TEXT NOT NULL,
                confidence REAL NOT NULL,
                pack_hash TEXT UNIQUE NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                last_validated_at TIMESTAMP,
                expires_at TIMESTAMP,
                validation_count INTEGER DEFAULT 0
            )
        """
        )

        cursor.execute("CREATE INDEX IF NOT EXISTS idx_web_cache_expires ON web_cache(expires_at)")
        cursor.execute(
            "CREATE INDEX IF NOT EXISTS idx_search_cache_expires ON search_cache(expires_at)"
        )
        cursor.execute(
            "CREATE INDEX IF NOT EXISTS idx_knowledge_packs_expires ON knowledge_packs(expires_at)"
        )

        conn.commit()
        conn.close()

        logger.info("Research cache database initialized")

    def run_research(
        self, query: str, max_pages: int = 5, force_refresh: bool = False
    ) -> KnowledgePack:
        """
        Run complete research pipeline for query.

        Args:
            query: Research query
            max_pages: Maximum pages to fetch (default 5)
            force_refresh: Force refresh even if cached

        Returns:
            KnowledgePack with synthesized information
        """
        logger.info(f"Starting research for: {query}")

        if not force_refresh:
            cached_pack = self.get_cached_pack(query)
            if cached_pack:
                logger.info("Using cached knowledge pack")
                return cached_pack

        search_results = self.search_provider.search(query, max_results=max_pages)

        if not search_results:
            logger.warning("No search results found, returning empty pack")
            return self._empty_pack(query)

        logger.info(f"Found {len(search_results)} search results")

        fetched_pages = []
        for result in search_results:
            logger.info(f"Fetching: {result.title}")
            fetch_result = self.fetcher.fetch_url(result.url)

            if fetch_result.status_code == 200 and fetch_result.text:
                fetched_pages.append(fetch_result)
                self._cache_fetch_result(fetch_result)
            else:
                logger.warning(f"Failed to fetch {result.url}: status {fetch_result.status_code}")

        if not fetched_pages:
            logger.warning("No pages fetched successfully")
            return self._empty_pack(query)

        logger.info(f"Successfully fetched {len(fetched_pages)} pages")

        pack = self._synthesize_pack_from_pages(query, fetched_pages)

        self._cache_knowledge_pack(pack)

        logger.info(f"Research complete: {pack.goal}")
        return pack

    def get_cached_pack(self, query: str) -> Optional[KnowledgePack]:
        """
        Get cached knowledge pack for query.

        Args:
            query: Research query

        Returns:
            Cached KnowledgePack or None
        """
        pack_hash = KnowledgePack(query=query, goal="").pack_hash

        conn = sqlite3.connect(str(self.cache_db_path))
        cursor = conn.cursor()

        cursor.execute(
            """
            SELECT pack_json, expires_at FROM knowledge_packs
            WHERE pack_hash = ?
        """,
            (pack_hash,),
        )

        row = cursor.fetchone()
        conn.close()

        if not row:
            return None

        pack_json, expires_at = row

        if expires_at:
            expiry_time = datetime.fromisoformat(expires_at)
            if datetime.now() > expiry_time:
                logger.info("Cached pack expired")
                return None

        logger.info("Found valid cached pack")
        pack_data = json.loads(pack_json)
        return KnowledgePack.from_dict(pack_data)

    def _synthesize_pack_from_pages(
        self, query: str, fetched_pages: List[FetchResult]
    ) -> KnowledgePack:
        """
        Synthesize knowledge pack from fetched pages using LLM.

        Args:
            query: Original research query
            fetched_pages: List of successfully fetched pages

        Returns:
            Synthesized KnowledgePack
        """
        logger.info("Synthesizing knowledge pack with LLM")

        pages_summary = self._prepare_pages_for_synthesis(fetched_pages)

        prompt = self._build_synthesis_prompt(query, pages_summary)

        try:
            response = self.llm_client.generate(prompt)
            pack_data = self._parse_llm_response(response, query, fetched_pages)
            return pack_data

        except Exception as e:
            logger.error(f"LLM synthesis failed: {e}")
            return self._fallback_pack(query, fetched_pages)

    def _prepare_pages_for_synthesis(self, fetched_pages: List[FetchResult]) -> str:
        """Prepare fetched pages summary for LLM."""
        summaries = []

        for i, page in enumerate(fetched_pages, start=1):
            summary = f"\n--- Source [{i}] ---\n"
            summary += f"Title: {page.title or 'Unknown'}\n"
            summary += f"URL: {page.final_url}\n"

            if page.headings:
                summary += f"Headings: {', '.join(page.headings[:5])}\n"

            if page.code_blocks:
                summary += f"Code blocks found: {len(page.code_blocks)}\n"
                for j, code in enumerate(page.code_blocks[:2], start=1):
                    summary += f"\nCode block {j}:\n```\n{code[:300]}...\n```\n"

            text_preview = page.text[:1000] if len(page.text) > 1000 else page.text
            summary += f"\nContent preview:\n{text_preview}\n"

            summaries.append(summary)

        return "\n".join(summaries)

    def _build_synthesis_prompt(self, query: str, pages_summary: str) -> str:
        """Build LLM prompt for knowledge pack synthesis."""
        prompt = f"""Given the following web pages about "{query}", """
        prompt += """extract a structured knowledge pack.

Your task is to analyze these sources and create a comprehensive guide with:
1. Goal: One sentence summary of what the user wants to accomplish
2. Assumptions: What we assume about the user's system/setup
3. Steps: Focused, substantial steps to accomplish the goal
   (each step: title, description, automated, manual, requires_verification)
4. Commands: Specific commands to run
   (command_text, language, platform, description)
5. File paths: Important file paths (path, purpose, optional)
6. Settings: Configuration settings (name, value, location, description)
7. Common errors: Known issues (error_message, cause, fix, source_index)
8. Confidence: Your confidence in this information (0.0-1.0)

Cite sources using [1], [2], etc. when providing information.

"""
        prompt += f"{pages_summary}\n\n"
        prompt += """Respond with a JSON object containing:
{
  "goal": "One sentence goal",
  "assumptions": ["assumption1", "assumption2"],
  "steps": [
    {"title": "Step title", "description": "What to do",
     "automated": true, "manual": false, "requires_verification": false}
  ],
  "commands": [
    {"command_text": "command", "language": "bash",
     "platform": "windows", "description": "What it does"}
  ],
  "file_paths": [
    {"path": "/path/to/file", "purpose": "Purpose", "optional": false}
  ],
  "settings": [
    {"name": "setting_name", "value": "value",
     "location": "where to set", "description": "what it does"}
  ],
  "common_errors": [
    {"error_message": "Error text", "cause": "Why it happens",
     "fix": "How to fix", "source_index": 1}
  ],
  "confidence": 0.8
}
"""
        return prompt

    def _parse_llm_response(
        self, response: str, query: str, fetched_pages: List[FetchResult]
    ) -> KnowledgePack:
        """Parse LLM response into KnowledgePack."""
        try:
            json_match = response.strip()
            if json_match.startswith("```json"):
                json_match = json_match[7:]
            if json_match.startswith("```"):
                json_match = json_match[3:]
            if json_match.endswith("```"):
                json_match = json_match[:-3]

            data = json.loads(json_match.strip())

            sources = [
                SourceEvidence(
                    url=page.final_url,
                    title=page.title or "Unknown",
                    snippet=page.text[:200],
                    fetched_at=datetime.now(),
                )
                for page in fetched_pages
            ]

            return KnowledgePack(
                query=query,
                goal=data.get("goal", ""),
                assumptions=data.get("assumptions", []),
                steps=data.get("steps", []),
                commands=data.get("commands", []),
                file_paths=data.get("file_paths", []),
                settings=data.get("settings", []),
                common_errors=data.get("common_errors", []),
                sources=sources,
                confidence=data.get("confidence", 0.7),
            )

        except Exception as e:
            logger.error(f"Failed to parse LLM response: {e}")
            return self._fallback_pack(query, fetched_pages)

    def _fallback_pack(self, query: str, fetched_pages: List[FetchResult]) -> KnowledgePack:
        """Create fallback knowledge pack when synthesis fails."""
        sources = [
            SourceEvidence(
                url=page.final_url,
                title=page.title or "Unknown",
                snippet=page.text[:200],
                fetched_at=datetime.now(),
            )
            for page in fetched_pages
        ]

        return KnowledgePack(
            query=query,
            goal=f"Research about: {query}",
            assumptions=["Information extracted from web sources"],
            steps=[
                {
                    "title": "Review sources",
                    "description": "Review the provided sources for information",
                    "automated": False,
                    "manual": True,
                    "requires_verification": False,
                }
            ],
            sources=sources,
            confidence=0.5,
        )

    def _empty_pack(self, query: str) -> KnowledgePack:
        """Create empty knowledge pack when research fails."""
        return KnowledgePack(
            query=query,
            goal=f"Unable to find information about: {query}",
            confidence=0.0,
        )

    def _cache_fetch_result(self, result: FetchResult) -> None:
        """Cache fetch result to database."""
        conn = sqlite3.connect(str(self.cache_db_path))
        cursor = conn.cursor()

        expires_at = datetime.now() + timedelta(days=14)

        cursor.execute(
            """
            INSERT OR REPLACE INTO web_cache
            (url, final_url, status_code, title, text, code_blocks, meta_description, expires_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
            (
                result.final_url,
                result.final_url,
                result.status_code,
                result.title,
                result.text,
                json.dumps(result.code_blocks),
                result.meta_description,
                expires_at.isoformat(),
            ),
        )

        conn.commit()
        conn.close()

    def _cache_knowledge_pack(self, pack: KnowledgePack) -> None:
        """Cache knowledge pack to database."""
        conn = sqlite3.connect(str(self.cache_db_path))
        cursor = conn.cursor()

        expires_at = datetime.now() + timedelta(days=30)

        cursor.execute(
            """
            INSERT OR REPLACE INTO knowledge_packs
            (id, query, pack_json, sources_json, confidence, pack_hash, expires_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
            (
                pack.pack_hash,
                pack.query,
                pack.to_json(),
                json.dumps([s.to_dict() for s in pack.sources]),
                pack.confidence,
                pack.pack_hash,
                expires_at.isoformat(),
            ),
        )

        conn.commit()
        conn.close()

        logger.info(f"Cached knowledge pack: {pack.pack_hash}")
