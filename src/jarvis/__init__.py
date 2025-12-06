"""
Jarvis: Advanced Windows AI Assistant with local LLM support
"""

__version__ = "0.1.0"

# Export main components for external use
from jarvis.action_executor import ActionExecutor, ActionResult
from jarvis.app import GUIApp, create_gui_app
from jarvis.brain.server import BrainServer, BrainServerError
from jarvis.chat import ChatMessage, ChatSession
from jarvis.config import JarvisConfig, LLMConfig, SafetyConfig, StorageConfig, ExecutionConfig, OCRConfig
from jarvis.container import Container
from jarvis.config import (
    BrainLLMConfig,
    DualLLMConfig,
    ExecutorLLMConfig,
    JarvisConfig,
    LLMConfig,
    SafetyConfig,
    StorageConfig,
)
from jarvis.container import Container, DualModelManager
from jarvis.executor.server import ExecutorServer, ExecutorServerError
from jarvis.llm_client import LLMClient, LLMConnectionError
from jarvis.memory_rag.rag_service import DocumentChunk, RAGMemoryService, RetrievalResult
from jarvis.orchestrator import Orchestrator
from jarvis.reasoning import Plan, PlanStep, ReasoningModule, SafetyFlag, StepStatus
from jarvis.system_actions import SystemActionRouter
from jarvis.tool_teaching import ToolTeachingModule
from jarvis.voice import VoiceInterface

__all__ = [
    "ActionExecutor",
    "ActionResult",
    "BrainLLMConfig",
    "BrainServer",
    "BrainServerError",
    "ChatMessage",
    "ChatSession",
    "Container",
    "ExecutionConfig",
    "create_gui_app",
    "GUIApp",
    "DocumentChunk",
    "DualLLMConfig",
    "DualModelManager",
    "ExecutorLLMConfig",
    "ExecutorServer",
    "ExecutorServerError",
    "Controller",
    "ControllerResult",
    "Dispatcher",
    "JarvisConfig",
    "LLMClient",
    "LLMConfig",
    "LLMConnectionError",
    "OCRConfig",
    "Orchestrator",
    "Plan",
    "PlanStep",
    "RAGMemoryService",
    "ReasoningModule",
    "RetrievalResult",
    "SafetyConfig",
    "SafetyFlag",
    "StepOutcome",
    "StepStatus",
    "StorageConfig",
    "SystemActionRouter",
    "ToolTeachingModule",
    "VoiceInterface",
]
