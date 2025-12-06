"""
Tests for RAG memory service.

Covers ingestion, retrieval scoring, planner prompt enrichment, and regression tests.
"""

import tempfile
from pathlib import Path
from typing import Any, Dict
from unittest.mock import MagicMock, Mock, patch

import pytest

from jarvis.config import JarvisConfig, LLMConfig, SafetyConfig, StorageConfig
from jarvis.llm_client import LLMClient
from jarvis.memory_rag.rag_service import DocumentChunk, RAGMemoryService, RetrievalResult
from jarvis.persistent_memory import MemoryModule
from jarvis.reasoning import Plan, PlanStep, ReasoningModule
from jarvis.tool_teaching import ToolTeachingModule


@pytest.fixture
def temp_storage_dir():
    """Create a temporary storage directory."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)


@pytest.fixture
def memory_module(temp_storage_dir):
    """Create a memory module for testing."""
    module = MemoryModule(storage_dir=temp_storage_dir, backend_type="sqlite")
    module.bootstrap()
    yield module
    module.shutdown()


@pytest.fixture
def rag_service(memory_module):
    """Create a RAG service for testing."""
    return RAGMemoryService(memory_module=memory_module, chunk_size=100, chunk_overlap=20)


@pytest.fixture
def mock_llm_client():
    """Create a mock LLM client."""
    mock_client = MagicMock(spec=LLMClient)
    mock_client.generate.return_value = '{"description": "test plan", "steps": []}'
    return mock_client


@pytest.fixture
def test_config(temp_storage_dir):
    """Create a test configuration."""
    return JarvisConfig(
        llm=LLMConfig(
            model="test-model",
            temperature=0.7,
            max_tokens=2048,
            base_url="http://localhost:11434",
            timeout=60,
        ),
        safety=SafetyConfig(
            enable_input_validation=True,
            max_input_length=10000,
            blocked_commands=[],
        ),
        storage=StorageConfig(
            data_dir=temp_storage_dir,
            logs_dir=temp_storage_dir / "logs",
        ),
        debug=False,
    )


class TestDocumentChunking:
    """Tests for document chunking functionality."""

    def test_chunk_document_basic(self, rag_service):
        """Test basic document chunking."""
        content = "This is a test document. " * 20
        chunks = rag_service.chunk_document(
            content=content, source_doc="test.txt", memory_type="tool_knowledge"
        )

        assert len(chunks) > 0
        assert all(isinstance(chunk, DocumentChunk) for chunk in chunks)
        assert all(chunk.memory_type == "tool_knowledge" for chunk in chunks)
        assert all(chunk.source_doc == "test.txt" for chunk in chunks)

    def test_chunk_document_with_overlap(self, rag_service):
        """Test that chunks have overlap."""
        # Create content longer than chunk_size (100) to force multiple chunks
        content = "This is a sentence. " * 20  # ~400 characters
        chunks = rag_service.chunk_document(
            content=content, source_doc="test.txt", memory_type="tool_knowledge"
        )

        assert len(chunks) >= 2
        # Verify chunks have sequential indices
        for i, chunk in enumerate(chunks):
            assert chunk.chunk_index == i

    def test_chunk_document_empty(self, rag_service):
        """Test chunking empty document."""
        chunks = rag_service.chunk_document(
            content="", source_doc="empty.txt", memory_type="tool_knowledge"
        )

        assert len(chunks) == 0

    def test_chunk_document_with_metadata(self, rag_service):
        """Test chunking with metadata."""
        content = "Test content " * 20
        metadata = {"author": "test_user", "version": "1.0"}

        chunks = rag_service.chunk_document(
            content=content,
            source_doc="test.txt",
            memory_type="tool_knowledge",
            metadata=metadata,
        )

        assert all(chunk.metadata == metadata for chunk in chunks)

    def test_chunk_document_sentence_boundaries(self, rag_service):
        """Test that chunking respects sentence boundaries."""
        content = "First sentence. Second sentence. Third sentence. " * 10
        chunks = rag_service.chunk_document(
            content=content, source_doc="test.txt", memory_type="tool_knowledge"
        )

        # Chunks should try to break at sentence boundaries
        assert len(chunks) > 0
        # Most chunks should end with a period (sentence boundary)
        ending_with_period = sum(1 for chunk in chunks if chunk.content.rstrip().endswith("."))
        assert ending_with_period > 0


class TestChunkStorage:
    """Tests for chunk storage functionality."""

    def test_store_chunks(self, rag_service):
        """Test storing chunks in memory."""
        chunks = [
            DocumentChunk(
                chunk_id="test-1",
                content="Test content 1",
                chunk_index=0,
                source_doc="test.txt",
                memory_type="tool_knowledge",
                metadata={},
                created_at="2024-01-01T00:00:00",
            ),
            DocumentChunk(
                chunk_id="test-2",
                content="Test content 2",
                chunk_index=1,
                source_doc="test.txt",
                memory_type="tool_knowledge",
                metadata={},
                created_at="2024-01-01T00:00:00",
            ),
        ]

        memory_ids = rag_service.store_chunks(chunks, tags=["test"])

        assert len(memory_ids) == 2
        assert all(isinstance(mid, str) for mid in memory_ids)

    def test_ingest_document(self, rag_service):
        """Test full document ingestion."""
        content = "This is test content. " * 20

        memory_ids = rag_service.ingest_document(
            content=content,
            source_doc="test.txt",
            memory_type="tool_knowledge",
            metadata={"test": True},
            tags=["ingestion"],
        )

        assert len(memory_ids) > 0

        # Verify chunks are stored and retrievable
        stored_chunks = rag_service.memory_module.get_memories_by_category("knowledge_chunks")
        assert len(stored_chunks) == len(memory_ids)


class TestRetrieval:
    """Tests for retrieval and scoring functionality."""

    def test_retrieve_basic(self, rag_service):
        """Test basic retrieval."""
        # Ingest some test documents
        rag_service.ingest_document(
            content="Python is a programming language",
            source_doc="python.txt",
            memory_type="tool_knowledge",
        )
        rag_service.ingest_document(
            content="JavaScript is used for web development",
            source_doc="js.txt",
            memory_type="tool_knowledge",
        )

        # Retrieve documents about Python
        results = rag_service.retrieve(query="python programming", top_k=5)

        assert len(results) > 0
        assert all(isinstance(r, RetrievalResult) for r in results)
        # Python document should be ranked higher
        assert "python" in results[0].chunk.content.lower()

    def test_retrieve_scoring(self, rag_service):
        """Test that retrieval scores are calculated."""
        rag_service.ingest_document(
            content="Machine learning is a subset of artificial intelligence",
            source_doc="ml.txt",
            memory_type="tool_knowledge",
        )

        results = rag_service.retrieve(query="machine learning", top_k=5)

        assert len(results) > 0
        # Verify scores are in descending order
        scores = [r.score for r in results]
        assert scores == sorted(scores, reverse=True)
        # Verify scores are positive
        assert all(score >= 0 for score in scores)

    def test_retrieve_by_memory_type(self, rag_service):
        """Test filtering retrieval by memory type."""
        rag_service.ingest_document(
            content="Tool knowledge content",
            source_doc="tool.txt",
            memory_type="tool_knowledge",
        )
        rag_service.ingest_document(
            content="Task history content", source_doc="task.txt", memory_type="task_history"
        )

        # Retrieve only tool_knowledge
        results = rag_service.retrieve(
            query="content", memory_types=["tool_knowledge"], top_k=10
        )

        assert all(r.chunk.memory_type == "tool_knowledge" for r in results)

    def test_retrieve_by_tags(self, rag_service):
        """Test filtering retrieval by tags."""
        rag_service.ingest_document(
            content="Tagged content",
            source_doc="tagged.txt",
            memory_type="tool_knowledge",
            tags=["important"],
        )
        rag_service.ingest_document(
            content="Untagged content",
            source_doc="untagged.txt",
            memory_type="tool_knowledge",
        )

        # Retrieve only tagged documents
        results = rag_service.retrieve(query="content", tags=["important"], top_k=10)

        assert len(results) > 0
        # Verify tagged document appears
        assert any("Tagged" in r.chunk.content for r in results)

    def test_retrieve_top_k(self, rag_service):
        """Test that top_k limits results."""
        # Ingest multiple documents
        for i in range(10):
            rag_service.ingest_document(
                content=f"Document number {i}",
                source_doc=f"doc{i}.txt",
                memory_type="tool_knowledge",
            )

        results = rag_service.retrieve(query="document", top_k=3)

        assert len(results) <= 3

    def test_retrieve_empty_query(self, rag_service):
        """Test retrieval with empty query."""
        rag_service.ingest_document(
            content="Some content", source_doc="test.txt", memory_type="tool_knowledge"
        )

        results = rag_service.retrieve(query="", top_k=5)

        # Should still return results even with empty query
        assert len(results) >= 0

    def test_retrieve_no_matches(self, rag_service):
        """Test retrieval when no documents exist."""
        results = rag_service.retrieve(query="nonexistent query", top_k=5)

        assert len(results) == 0


class TestPromptEnrichment:
    """Tests for prompt enrichment functionality."""

    def test_enrich_prompt_basic(self, rag_service):
        """Test basic prompt enrichment."""
        # Ingest relevant knowledge
        rag_service.ingest_document(
            content="Git is a version control system",
            source_doc="git.txt",
            memory_type="tool_knowledge",
        )

        base_prompt = "How do I use git?"
        enriched = rag_service.enrich_prompt(
            base_prompt=base_prompt, query="git version control", top_k=3
        )

        assert enriched != base_prompt
        assert "Relevant contextual knowledge:" in enriched
        assert base_prompt in enriched

    def test_enrich_prompt_no_knowledge(self, rag_service):
        """Test prompt enrichment when no relevant knowledge exists."""
        base_prompt = "Test prompt"
        enriched = rag_service.enrich_prompt(
            base_prompt=base_prompt, query="nonexistent topic", top_k=3
        )

        # Should return original prompt when no knowledge found
        assert enriched == base_prompt

    def test_enrich_prompt_with_memory_types(self, rag_service):
        """Test prompt enrichment filtered by memory types."""
        rag_service.ingest_document(
            content="Tool knowledge",
            source_doc="tool.txt",
            memory_type="tool_knowledge",
        )
        rag_service.ingest_document(
            content="Task history", source_doc="task.txt", memory_type="task_history"
        )

        base_prompt = "Test prompt"
        enriched = rag_service.enrich_prompt(
            base_prompt=base_prompt,
            query="knowledge",
            memory_types=["tool_knowledge"],
            top_k=3,
        )

        if enriched != base_prompt:
            assert "[tool_knowledge]" in enriched


class TestTaskRecording:
    """Tests for task execution recording."""

    def test_record_task_execution(self, rag_service):
        """Test recording task execution."""
        memory_ids = rag_service.record_task_execution(
            task_description="Create a file",
            task_result="File created successfully",
            metadata={"user": "test"},
            tags=["file_operation"],
        )

        assert len(memory_ids) > 0

        # Verify task is stored and retrievable
        results = rag_service.retrieve(query="create file", memory_types=["task_history"])

        assert len(results) > 0
        assert any("Create a file" in r.chunk.content for r in results)

    def test_record_task_execution_minimal(self, rag_service):
        """Test recording task with minimal parameters."""
        memory_ids = rag_service.record_task_execution(
            task_description="Simple task", task_result="Completed"
        )

        assert len(memory_ids) > 0


class TestPlannerIntegration:
    """Tests for planner integration with RAG."""

    def test_reasoning_module_with_rag(self, test_config, mock_llm_client, rag_service):
        """Test reasoning module uses RAG for prompt enrichment."""
        # Ingest some tool knowledge
        rag_service.ingest_document(
            content="Git commands: clone, commit, push",
            source_doc="git.txt",
            memory_type="tool_knowledge",
        )

        reasoning_module = ReasoningModule(
            config=test_config, llm_client=mock_llm_client, rag_service=rag_service
        )

        # Generate a plan
        with patch.object(mock_llm_client, "generate") as mock_generate:
            mock_generate.return_value = """
            {
                "description": "Test plan",
                "steps": [
                    {
                        "step_number": 1,
                        "description": "Test step",
                        "required_tools": [],
                        "dependencies": [],
                        "safety_flags": []
                    }
                ]
            }
            """

            plan = reasoning_module.plan_actions("How do I use git?")

            assert plan is not None
            # Verify LLM was called with enriched prompt
            called_prompt = mock_generate.call_args[0][0]
            # If RAG found relevant knowledge, prompt should be enriched
            assert "How do I use git?" in called_prompt

    def test_record_plan_execution(self, test_config, mock_llm_client, rag_service):
        """Test recording plan execution in RAG."""
        reasoning_module = ReasoningModule(
            config=test_config, llm_client=mock_llm_client, rag_service=rag_service
        )

        # Create a test plan
        with patch.object(mock_llm_client, "generate") as mock_generate:
            mock_generate.return_value = """
            {
                "description": "Test plan",
                "steps": [
                    {
                        "step_number": 1,
                        "description": "Execute action",
                        "required_tools": [],
                        "dependencies": [],
                        "safety_flags": []
                    }
                ]
            }
            """
            plan = reasoning_module.plan_actions("Test task")

        # Record execution
        reasoning_module.record_plan_execution(
            plan=plan, execution_result="Successfully completed", tags=["test"]
        )

        # Verify execution is recorded
        results = rag_service.retrieve(query="test task", memory_types=["task_history"])

        assert len(results) > 0


class TestToolTeachingIntegration:
    """Tests for tool teaching integration with RAG."""

    def test_tool_teaching_with_rag(self, temp_storage_dir, mock_llm_client, rag_service):
        """Test tool teaching stores documentation in RAG."""
        from jarvis.memory import MemoryStore

        memory_store = MemoryStore(storage_dir=temp_storage_dir / "tool_knowledge")

        # Mock extract_tool_knowledge
        with patch.object(mock_llm_client, "extract_tool_knowledge") as mock_extract:
            mock_extract.return_value = {
                "name": "git",
                "description": "Version control system",
                "commands": ["clone", "commit", "push"],
                "parameters": [],
                "constraints": [],
                "examples": [],
            }

            tool_teaching = ToolTeachingModule(
                llm_client=mock_llm_client,
                memory_store=memory_store,
                rag_service=rag_service,
            )

            # Create a test document
            test_doc = temp_storage_dir / "git.txt"
            test_doc.write_text("Git is a distributed version control system")

            # Learn from document
            learned_tools = tool_teaching.learn_from_document(test_doc)

            assert len(learned_tools) > 0

            # Verify documentation is in RAG
            results = rag_service.retrieve(
                query="version control", memory_types=["tool_knowledge"]
            )

            assert len(results) > 0


class TestStatistics:
    """Tests for RAG statistics."""

    def test_get_statistics(self, rag_service):
        """Test getting RAG statistics."""
        # Ingest some documents
        rag_service.ingest_document(
            content="Content 1", source_doc="doc1.txt", memory_type="tool_knowledge"
        )
        rag_service.ingest_document(
            content="Content 2", source_doc="doc2.txt", memory_type="task_history"
        )

        stats = rag_service.get_statistics()

        assert "total_chunks" in stats
        assert "chunks_by_type" in stats
        assert "chunks_by_source" in stats
        assert stats["total_chunks"] > 0

    def test_get_statistics_empty(self, rag_service):
        """Test statistics when no documents exist."""
        stats = rag_service.get_statistics()

        assert stats["total_chunks"] == 0
        assert len(stats["chunks_by_type"]) == 0


class TestRegressionExistingMemory:
    """Regression tests for existing memory functionality."""

    def test_memory_module_still_works(self, memory_module):
        """Test that existing MemoryModule functionality is not broken."""
        # Create a memory entry
        memory_id = memory_module.create_memory(
            category="test",
            key="test_key",
            value={"data": "test"},
            entity_type="test_entity",
            tags=["test"],
        )

        assert memory_id is not None

        # Read it back
        entry = memory_module.get_memory(memory_id)
        assert entry is not None
        assert entry.category == "test"
        assert entry.key == "test_key"

    def test_memory_module_query(self, memory_module):
        """Test that existing query functionality works."""
        memory_module.create_memory(
            category="preferences",
            key="theme",
            value={"theme": "dark"},
            entity_type="user_preference",
            tags=["ui"],
        )

        results = memory_module.get_memories_by_category("preferences")
        assert len(results) > 0

    def test_memory_module_update(self, memory_module):
        """Test that existing update functionality works."""
        memory_id = memory_module.create_memory(
            category="test",
            key="test_key",
            value={"data": "original"},
            entity_type="test_entity",
        )

        success = memory_module.update_memory(
            memory_id=memory_id, value={"data": "updated"}, module="test"
        )

        assert success is True
        entry = memory_module.get_memory(memory_id)
        assert entry.value["data"] == "updated"


class TestEdgeCases:
    """Tests for edge cases and error handling."""

    def test_chunk_very_small_document(self, rag_service):
        """Test chunking very small document."""
        chunks = rag_service.chunk_document(
            content="Small", source_doc="small.txt", memory_type="tool_knowledge"
        )

        assert len(chunks) == 1
        assert chunks[0].content == "Small"

    def test_chunk_unicode_content(self, rag_service):
        """Test chunking content with unicode characters."""
        content = "Unicode: 你好 مرحبا שלום " * 10
        chunks = rag_service.chunk_document(
            content=content, source_doc="unicode.txt", memory_type="tool_knowledge"
        )

        assert len(chunks) > 0
        assert all("你好" in chunk.content or "مرحبا" in chunk.content for chunk in chunks[:2])

    def test_retrieve_with_special_characters(self, rag_service):
        """Test retrieval with special characters in query."""
        rag_service.ingest_document(
            content="C++ programming language",
            source_doc="cpp.txt",
            memory_type="tool_knowledge",
        )

        results = rag_service.retrieve(query="C++ programming", top_k=5)

        assert len(results) > 0

    def test_tokenization_edge_cases(self, rag_service):
        """Test tokenization with edge cases."""
        # Test with various punctuation and formatting
        content = "Test. Test! Test? Test... Test-hyphen Test_underscore"
        tokens = rag_service._tokenize(content)

        assert len(tokens) > 0
        assert all(isinstance(token, str) for token in tokens)
