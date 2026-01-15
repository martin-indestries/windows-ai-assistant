"""
Spectral: Advanced Windows AI Assistant with local LLM support
"""

__version__ = "0.1.0"

# Export main components for external use
from spectral.action_executor import ActionExecutor, ActionResult
from spectral.app import GUIApp, create_gui_app
from spectral.brain.server import BrainServer, BrainServerError
from spectral.chat import ChatMessage, ChatSession
from spectral.code_cleaner import CodeCleaner
from spectral.config import (
    BrainLLMConfig,
    DualLLMConfig,
    ExecutionConfig,
    ExecutorLLMConfig,
    JarvisConfig,
    LLMConfig,
    OCRConfig,
    SafetyConfig,
    StorageConfig,
)
from spectral.container import Container, DualModelManager
from spectral.conversation_context import ConversationContext, ConversationTurn
from spectral.execution_debugger import ExecutionDebugger
from spectral.executor.server import ExecutorServer, ExecutorServerError
from spectral.interactive_executor import InteractiveExecutor
from spectral.interactive_program_analyzer import InteractiveProgramAnalyzer, ProgramType
from spectral.llm_client import LLMClient, LLMConnectionError
from spectral.memory_rag.rag_service import DocumentChunk, RAGMemoryService, RetrievalResult
from spectral.mistake_learner import LearningPattern, MistakeLearner
from spectral.orchestrator import Orchestrator
from spectral.output_validator import OutputValidator
from spectral.program_deployer import ProgramDeployer
from spectral.reasoning import Plan, PlanStep, ReasoningModule, SafetyFlag, StepStatus
# from spectral.sandbox_execution_system import SandboxExecutionSystem  # Disabled - using new SandboxRunManager
from spectral.sandbox_manager import SandboxRunManager, SandboxResult
from spectral.system_actions import SystemActionRouter
from spectral.test_case_generator import TestCaseGenerator
from spectral.tool_teaching import ToolTeachingModule
from spectral.voice import VoiceInterface

__all__ = [
    "ActionExecutor",
    "ActionResult",
    "BrainLLMConfig",
    "BrainServer",
    "BrainServerError",
    "ChatMessage",
    "ChatSession",
    "CodeCleaner",
    "ConversationContext",
    "ConversationTurn",
    "Container",
    "ExecutionConfig",
    "ExecutionDebugger",
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
    "InteractiveExecutor",
    "InteractiveProgramAnalyzer",
    "JarvisConfig",
    "LLMClient",
    "LLMConfig",
    "LLMConnectionError",
    "LearningPattern",
    "MistakeLearner",
    "OCRConfig",
    "Orchestrator",
    "OutputValidator",
    "Plan",
    "PlanStep",
    "ProgramDeployer",
    "ProgramType",
    "RAGMemoryService",
    "ReasoningModule",
    "RetrievalResult",
    "SafetyConfig",
    "SandboxRunManager",
    "SandboxResult",
    "SafetyFlag",
    "StepOutcome",
    "StepStatus",
    "StorageConfig",
    "SystemActionRouter",
    "TestCaseGenerator",
    "ToolTeachingModule",
    "VoiceInterface",
]
