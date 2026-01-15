"""
Knowledge pack data models for research pipeline.

Defines structured knowledge extracted from web research for task planning
and execution.
"""

import hashlib
import json
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional


@dataclass
class SourceEvidence:
    """Evidence from a web source supporting a claim or instruction."""

    url: str
    title: str
    snippet: str
    fetched_at: datetime

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "url": self.url,
            "title": self.title,
            "snippet": self.snippet,
            "fetched_at": self.fetched_at.isoformat(),
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "SourceEvidence":
        """Create from dictionary."""
        return cls(
            url=data["url"],
            title=data["title"],
            snippet=data["snippet"],
            fetched_at=datetime.fromisoformat(data["fetched_at"]),
        )


@dataclass
class KnowledgePack:
    """
    Structured knowledge pack from web research.

    Contains actionable information extracted from multiple sources:
    - Goal and assumptions
    - Steps to accomplish the task
    - Commands, file paths, settings
    - Common errors and solutions
    - Source evidence for verification
    """

    query: str
    goal: str
    assumptions: List[str] = field(default_factory=list)
    steps: List[Dict[str, Any]] = field(default_factory=list)
    commands: List[Dict[str, Any]] = field(default_factory=list)
    file_paths: List[Dict[str, Any]] = field(default_factory=list)
    settings: List[Dict[str, Any]] = field(default_factory=list)
    common_errors: List[Dict[str, Any]] = field(default_factory=list)
    sources: List[SourceEvidence] = field(default_factory=list)
    confidence: float = 0.7
    created_at: datetime = field(default_factory=datetime.now)
    pack_hash: str = field(init=False)

    def __post_init__(self):
        """Compute pack hash after initialization."""
        self.pack_hash = self._compute_hash()

    def _compute_hash(self) -> str:
        """Compute SHA256 hash of query for deduplication."""
        query_normalized = self.query.lower().strip()
        return hashlib.sha256(query_normalized.encode()).hexdigest()

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "query": self.query,
            "goal": self.goal,
            "assumptions": self.assumptions,
            "steps": self.steps,
            "commands": self.commands,
            "file_paths": self.file_paths,
            "settings": self.settings,
            "common_errors": self.common_errors,
            "sources": [s.to_dict() for s in self.sources],
            "confidence": self.confidence,
            "created_at": self.created_at.isoformat(),
            "pack_hash": self.pack_hash,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "KnowledgePack":
        """Create from dictionary."""
        sources = [SourceEvidence.from_dict(s) for s in data.get("sources", [])]
        return cls(
            query=data["query"],
            goal=data["goal"],
            assumptions=data.get("assumptions", []),
            steps=data.get("steps", []),
            commands=data.get("commands", []),
            file_paths=data.get("file_paths", []),
            settings=data.get("settings", []),
            common_errors=data.get("common_errors", []),
            sources=sources,
            confidence=data.get("confidence", 0.7),
            created_at=datetime.fromisoformat(data["created_at"]),
        )

    def to_json(self) -> str:
        """Serialize to JSON string."""
        return json.dumps(self.to_dict(), indent=2)

    @classmethod
    def from_json(cls, json_str: str) -> "KnowledgePack":
        """Deserialize from JSON string."""
        data = json.loads(json_str)
        return cls.from_dict(data)


@dataclass
class SearchResult:
    """A single search result from a search provider."""

    title: str
    url: str
    snippet: str
    rank: int

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "title": self.title,
            "url": self.url,
            "snippet": self.snippet,
            "rank": self.rank,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "SearchResult":
        """Create from dictionary."""
        return cls(
            title=data["title"],
            url=data["url"],
            snippet=data["snippet"],
            rank=data["rank"],
        )


@dataclass
class FetchResult:
    """Result of fetching and extracting content from a URL."""

    final_url: str
    status_code: int
    html: Optional[str] = None
    text: str = ""
    title: Optional[str] = None
    headings: List[str] = field(default_factory=list)
    code_blocks: List[str] = field(default_factory=list)
    meta_description: Optional[str] = None
    fetch_time: float = 0.0
    fetcher_used: str = "requests"

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "final_url": self.final_url,
            "status_code": self.status_code,
            "text": self.text,
            "title": self.title,
            "headings": self.headings,
            "code_blocks": self.code_blocks,
            "meta_description": self.meta_description,
            "fetch_time": self.fetch_time,
            "fetcher_used": self.fetcher_used,
        }
