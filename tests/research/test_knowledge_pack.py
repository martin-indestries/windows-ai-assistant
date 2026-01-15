"""Tests for knowledge pack data models."""

from datetime import datetime

from spectral.research.knowledge_pack import KnowledgePack, SourceEvidence


def test_source_evidence_serialization():
    """Test SourceEvidence serialization and deserialization."""
    source = SourceEvidence(
        url="https://example.com",
        title="Example Title",
        snippet="This is a snippet",
        fetched_at=datetime(2024, 1, 1, 12, 0, 0),
    )

    data = source.to_dict()
    assert data["url"] == "https://example.com"
    assert data["title"] == "Example Title"

    restored = SourceEvidence.from_dict(data)
    assert restored.url == source.url
    assert restored.title == source.title


def test_knowledge_pack_hash_generation():
    """Test that knowledge pack generates consistent hash."""
    pack1 = KnowledgePack(query="How to install Python", goal="Install Python")
    pack2 = KnowledgePack(query="how to install python", goal="Install Python")

    assert pack1.pack_hash == pack2.pack_hash


def test_knowledge_pack_serialization():
    """Test KnowledgePack serialization and deserialization."""
    sources = [
        SourceEvidence(
            url="https://example.com",
            title="Example",
            snippet="Snippet",
            fetched_at=datetime(2024, 1, 1, 12, 0, 0),
        )
    ]

    pack = KnowledgePack(
        query="Test query",
        goal="Test goal",
        assumptions=["Assumption 1"],
        steps=[{"title": "Step 1", "description": "Do something"}],
        sources=sources,
        confidence=0.8,
    )

    json_str = pack.to_json()
    restored = KnowledgePack.from_json(json_str)

    assert restored.query == pack.query
    assert restored.goal == pack.goal
    assert len(restored.sources) == len(pack.sources)
    assert restored.confidence == pack.confidence


def test_knowledge_pack_empty():
    """Test creating minimal knowledge pack."""
    pack = KnowledgePack(query="Test", goal="Goal")

    assert pack.query == "Test"
    assert pack.goal == "Goal"
    assert len(pack.assumptions) == 0
    assert len(pack.steps) == 0
    assert pack.confidence == 0.7
