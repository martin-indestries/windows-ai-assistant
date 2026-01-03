"""
Dependency injection container module.

Manages creation and wiring of application dependencies to keep modules
loosely coupled and independently testable.
"""

import logging
from typing import Optional

from jarvis.action_executor import ActionExecutor
from jarvis.brain.server import BrainServer, BrainServerError
from jarvis.config import ConfigLoader, JarvisConfig
from jarvis.dual_execution_orchestrator import DualExecutionOrchestrator
from jarvis.executor.server import ExecutorServer, ExecutorServerError
from jarvis.llm_client import LLMClient
from jarvis.logging_config import setup_logging
from jarvis.memory import MemoryStore
from jarvis.memory_rag.rag_service import RAGMemoryService
from jarvis.orchestrator import Orchestrator
from jarvis.persistent_memory import MemoryModule
from jarvis.reasoning import ReasoningModule
from jarvis.tool_teaching import ToolTeachingModule

logger = logging.getLogger(__name__)


class DualModelManager:
    """
    Manager for dual-model setup (Brain + Executor).

    Bootstraps both servers, tests connectivity, and provides access
    to brain and executor services.
    """

    def __init__(self, config: JarvisConfig) -> None:
        """
        Initialize dual model manager.

        Args:
            config: Jarvis configuration with dual_llm settings
        """
        self.config = config
        self._brain_server: Optional[BrainServer] = None
        self._executor_server: Optional[ExecutorServer] = None

        if config.dual_llm.enabled:
            logger.info("Dual-model mode enabled, initializing brain and executor servers")
            self._initialize_servers()
        else:
            logger.info("Dual-model mode disabled, using single LLM configuration")

    def _initialize_servers(self) -> None:
        """Initialize both brain and executor servers."""
        # Initialize Brain server
        try:
            self._brain_server = BrainServer(config=self.config.dual_llm.brain)
            logger.info("Brain server initialized successfully")
        except BrainServerError as e:
            logger.error(f"Failed to initialize Brain server: {e}")
            self._brain_server = None

        # Initialize Executor server
        try:
            self._executor_server = ExecutorServer(config=self.config.dual_llm.executor)
            logger.info("Executor server initialized successfully")
        except ExecutorServerError as e:
            logger.error(f"Failed to initialize Executor server: {e}")
            self._executor_server = None

    def get_brain_server(self) -> Optional[BrainServer]:
        """
        Get the brain server instance.

        Returns:
            BrainServer instance or None if not initialized
        """
        return self._brain_server

    def get_executor_server(self) -> Optional[ExecutorServer]:
        """
        Get the executor server instance.

        Returns:
            ExecutorServer instance or None if not initialized
        """
        return self._executor_server

    def is_dual_mode_enabled(self) -> bool:
        """
        Check if dual-model mode is enabled and working.

        Returns:
            True if both servers are initialized, False otherwise
        """
        return (
            self.config.dual_llm.enabled
            and self._brain_server is not None
            and self._executor_server is not None
        )

    def test_connectivity(self) -> dict:
        """
        Test connectivity to both servers.

        Returns:
            Dictionary with connection status for each server
        """
        result = {
            "dual_mode_enabled": self.config.dual_llm.enabled,
            "brain_server": {
                "initialized": self._brain_server is not None,
                "model": self.config.dual_llm.brain.model if self._brain_server else None,
            },
            "executor_server": {
                "initialized": self._executor_server is not None,
                "model": self.config.dual_llm.executor.model if self._executor_server else None,
            },
        }
        return result


class Container:
    """Dependency injection container."""

    def __init__(self) -> None:
        """Initialize the dependency container."""
        self._config_loader: Optional[ConfigLoader] = None
        self._config: Optional[JarvisConfig] = None
        self._orchestrator: Optional[Orchestrator] = None
        self._llm_client: Optional[LLMClient] = None
        self._memory_store: Optional[MemoryStore] = None
        self._memory_module: Optional[MemoryModule] = None
        self._rag_service: Optional[RAGMemoryService] = None
        self._tool_teaching_module: Optional[ToolTeachingModule] = None
        self._reasoning_module: Optional[ReasoningModule] = None
        self._action_executor: Optional[ActionExecutor] = None
        self._system_action_router = None
        self._dual_model_manager: Optional[DualModelManager] = None
        self._dual_execution_orchestrator: Optional[DualExecutionOrchestrator] = None

    def get_config_loader(self, config_path: Optional[str] = None) -> ConfigLoader:
        """
        Get or create the configuration loader.

        Args:
            config_path: Optional path to configuration file

        Returns:
            ConfigLoader instance
        """
        if self._config_loader is None:
            self._config_loader = ConfigLoader(config_path=config_path)
        return self._config_loader

    def get_config(self, config_path: Optional[str] = None) -> JarvisConfig:
        """
        Get or create the configuration.

        Args:
            config_path: Optional path to configuration file

        Returns:
            JarvisConfig instance
        """
        if self._config is None:
            loader = self.get_config_loader(config_path=config_path)
            self._config = loader.load()
            self._setup_logging()
        return self._config

    def _setup_logging(self) -> None:
        """Set up logging based on configuration."""
        if self._config is None:
            return

        log_level = logging.DEBUG if self._config.debug else logging.INFO
        setup_logging(
            level=log_level,
            log_dir=self._config.storage.logs_dir,
        )

    def get_orchestrator(self, config_path: Optional[str] = None) -> Orchestrator:
        """
        Get or create the orchestrator.

        Args:
            config_path: Optional path to configuration file

        Returns:
            Orchestrator instance
        """
        if self._orchestrator is None:
            config = self.get_config(config_path=config_path)
            memory_store = self.get_memory_store(config_path=config_path)
            system_action_router = self.get_system_action_router(config_path=config_path)

            # Extract execution config for verification and retry settings
            enable_verification = True
            enable_retry = True
            max_retries = 3

            try:
                config_dict = config.model_dump()
                if "execution" in config_dict:
                    exec_config = config_dict["execution"]
                    enable_verification = exec_config.get("enable_verification", True)
                    enable_retry = exec_config.get("enable_retry", True)
                    max_retries = exec_config.get("max_retries", 3)
            except Exception:
                pass

            self._orchestrator = Orchestrator(
                config=config,
                memory_store=memory_store,
                system_action_router=system_action_router,
                enable_verification=enable_verification,
                enable_retry=enable_retry,
                max_retries=max_retries,
            )
        return self._orchestrator

    def get_llm_client(self, config_path: Optional[str] = None) -> LLMClient:
        """
        Get or create the LLM client.

        Args:
            config_path: Optional path to configuration file

        Returns:
            LLMClient instance
        """
        if self._llm_client is None:
            config = self.get_config(config_path=config_path)
            self._llm_client = LLMClient(config=config.llm)
        return self._llm_client

    def get_memory_store(self, config_path: Optional[str] = None) -> MemoryStore:
        """
        Get or create the memory store.

        Args:
            config_path: Optional path to configuration file

        Returns:
            MemoryStore instance
        """
        if self._memory_store is None:
            config = self.get_config(config_path=config_path)
            storage_dir = config.storage.data_dir / "tool_knowledge"
            self._memory_store = MemoryStore(storage_dir=storage_dir)
        return self._memory_store

    def get_memory_module(self, config_path: Optional[str] = None) -> MemoryModule:
        """
        Get or create the persistent memory module.

        Args:
            config_path: Optional path to configuration file

        Returns:
            MemoryModule instance
        """
        if self._memory_module is None:
            config = self.get_config(config_path=config_path)
            storage_dir = config.storage.data_dir / "persistent_memory"
            self._memory_module = MemoryModule(storage_dir=storage_dir, backend_type="sqlite")
        return self._memory_module

    def get_rag_service(self, config_path: Optional[str] = None) -> RAGMemoryService:
        """
        Get or create the RAG memory service.

        Args:
            config_path: Optional path to configuration file

        Returns:
            RAGMemoryService instance
        """
        if self._rag_service is None:
            memory_module = self.get_memory_module(config_path=config_path)
            self._rag_service = RAGMemoryService(
                memory_module=memory_module, chunk_size=500, chunk_overlap=50
            )
        return self._rag_service

    def get_tool_teaching_module(self, config_path: Optional[str] = None) -> ToolTeachingModule:
        """
        Get or create the tool teaching module.

        Args:
            config_path: Optional path to configuration file

        Returns:
            ToolTeachingModule instance
        """
        if self._tool_teaching_module is None:
            llm_client = self.get_llm_client(config_path=config_path)
            memory_store = self.get_memory_store(config_path=config_path)
            rag_service = self.get_rag_service(config_path=config_path)
            self._tool_teaching_module = ToolTeachingModule(
                llm_client=llm_client, memory_store=memory_store, rag_service=rag_service
            )
        return self._tool_teaching_module

    def get_reasoning_module(self, config_path: Optional[str] = None) -> ReasoningModule:
        """
        Get or create the reasoning module.

        Args:
            config_path: Optional path to configuration file

        Returns:
            ReasoningModule instance
        """
        if self._reasoning_module is None:
            config = self.get_config(config_path=config_path)
            llm_client = self.get_llm_client(config_path=config_path)
            rag_service = self.get_rag_service(config_path=config_path)
            self._reasoning_module = ReasoningModule(
                config=config, llm_client=llm_client, rag_service=rag_service
            )
        return self._reasoning_module

    def get_action_executor(self, config_path: Optional[str] = None) -> ActionExecutor:
        """
        Get or create the action executor.

        Args:
            config_path: Optional path to configuration file

        Returns:
            ActionExecutor instance
        """
        if self._action_executor is None:
            config = self.get_config(config_path=config_path)
            # Extract execution config if available
            allowed_dirs = None
            disallowed_dirs = None
            dry_run = False
            action_timeout = 30

            # Try to get execution configuration from config dict
            try:
                config_dict = config.model_dump()
                if "execution" in config_dict:
                    exec_config = config_dict["execution"]
                    allowed_dirs = exec_config.get("allowed_directories")
                    disallowed_dirs = exec_config.get("disallowed_directories")
                    dry_run = exec_config.get("dry_run", False)
                    action_timeout = exec_config.get("action_timeout", 30)
            except Exception:
                pass

            self._action_executor = ActionExecutor(
                allowed_directories=allowed_dirs,
                disallowed_directories=disallowed_dirs,
                dry_run=dry_run,
                action_timeout=action_timeout,
            )
        return self._action_executor

    def get_system_action_router(self, config_path: Optional[str] = None):
        """
        Get or create the system action router.

        Args:
            config_path: Optional path to configuration file

        Returns:
            SystemActionRouter instance
        """
        if self._system_action_router is None:
            action_executor = self.get_action_executor(config_path=config_path)
            config = self.get_config(config_path=config_path)

            # Extract execution config if available
            dry_run = False
            action_timeout = 30
            tesseract_path = None

            try:
                config_dict = config.model_dump()
                if "execution" in config_dict:
                    exec_config = config_dict["execution"]
                    dry_run = exec_config.get("dry_run", False)
                    action_timeout = exec_config.get("action_timeout", 30)
                if "ocr" in config_dict:
                    tesseract_path = config_dict["ocr"].get("tesseract_path")
            except Exception:
                pass

            from jarvis.system_actions import SystemActionRouter

            self._system_action_router = SystemActionRouter(
                action_executor=action_executor,
                dry_run=dry_run,
                tesseract_path=tesseract_path,
                action_timeout=action_timeout,
            )
        return self._system_action_router

    def get_dual_model_manager(self, config_path: Optional[str] = None) -> DualModelManager:
        """
        Get or create the dual model manager.

        Args:
            config_path: Optional path to configuration file

        Returns:
            DualModelManager instance
        """
        if self._dual_model_manager is None:
            config = self.get_config(config_path=config_path)
            self._dual_model_manager = DualModelManager(config=config)
        return self._dual_model_manager

    def get_dual_execution_orchestrator(self, config_path: Optional[str] = None) -> DualExecutionOrchestrator:
        """
        Get or create the dual execution orchestrator.

        Args:
            config_path: Optional path to configuration file

        Returns:
            DualExecutionOrchestrator instance
        """
        if self._dual_execution_orchestrator is None:
            llm_client = self.get_llm_client(config_path=config_path)
            self._dual_execution_orchestrator = DualExecutionOrchestrator(llm_client=llm_client)
        return self._dual_execution_orchestrator

