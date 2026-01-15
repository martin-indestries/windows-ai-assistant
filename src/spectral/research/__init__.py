"""
Web research pipeline for Spectral.

Provides free web research capabilities using DuckDuckGo scraping,
content extraction, and LLM synthesis into structured knowledge packs.

No API keys or paid services required.
"""

from spectral.research.knowledge_pack import (
    FetchResult,
    KnowledgePack,
    SearchResult,
    SourceEvidence,
)
from spectral.research.research_orchestrator import ResearchOrchestrator

__all__ = [
    "ResearchOrchestrator",
    "KnowledgePack",
    "SourceEvidence",
    "SearchResult",
    "FetchResult",
]
