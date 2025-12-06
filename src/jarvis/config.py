"""
Configuration loading and management module.

Handles loading settings from YAML/JSON files with support for:
- LLM provider configuration
- Safety toggles
- Storage paths
"""

import json
import logging
import os
from pathlib import Path
from typing import Any, Dict, Optional, Union

import yaml
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)


class LLMConfig(BaseModel):
    """Configuration for LLM provider."""

    provider: str = Field(default="ollama", description="LLM provider (e.g., ollama, local)")
    model: str = Field(default="llama3", description="Model name or path")
    base_url: Optional[str] = Field(
        default="http://localhost:11434", description="Base URL for provider"
    )
    temperature: float = Field(default=0.7, ge=0.0, le=2.0)
    max_tokens: int = Field(default=2048, ge=1)
    timeout: int = Field(default=60, ge=1, description="Request timeout in seconds")


class BrainLLMConfig(BaseModel):
    """Configuration for the Brain LLM (reasoning/planning model)."""

    provider: str = Field(default="ollama", description="LLM provider (e.g., ollama, local)")
    model: str = Field(
        default="deepseek-r1:70b-qwen-distill-q4_K_M",
        description="Model name for reasoning (DeepSeek-R1-Distill-Llama-70B Q4_K_M recommended)",
    )
    base_url: Optional[str] = Field(
        default="http://localhost:11434", description="Base URL for provider"
    )
    temperature: float = Field(
        default=0.5, ge=0.0, le=2.0, description="Lower temperature for more deterministic reasoning"
    )
    max_tokens: int = Field(default=4096, ge=1, description="Larger token limit for detailed plans")
    timeout: int = Field(
        default=120, ge=1, description="Longer timeout for reasoning (2+ minutes recommended)"
    )
    # Hardware hints for Ollama configuration
    num_gpu: int = Field(
        default=1, ge=0, description="Number of GPU layers to use (0 for CPU-only)"
    )
    num_thread: int = Field(
        default=8, ge=1, description="Number of CPU threads for inference"
    )
    num_ctx: int = Field(default=8192, ge=1, description="Context window size")
    cpu_ram_gb: int = Field(
        default=64, ge=1, description="Recommended CPU RAM in GB (for resource planning)"
    )
    gpu_vram_gb: int = Field(
        default=24, ge=0, description="Recommended GPU VRAM in GB (0 if CPU-only)"
    )


class ExecutorLLMConfig(BaseModel):
    """Configuration for the Executor LLM (fast execution model)."""

    provider: str = Field(default="ollama", description="LLM provider (e.g., ollama, local)")
    model: str = Field(
        default="llama3.1:8b",
        description="Model name for execution (LLaMA 3.1 8B/12B recommended)",
    )
    base_url: Optional[str] = Field(
        default="http://localhost:11434", description="Base URL for provider"
    )
    temperature: float = Field(
        default=0.7, ge=0.0, le=2.0, description="Moderate temperature for natural responses"
    )
    max_tokens: int = Field(default=2048, ge=1, description="Standard token limit")
    timeout: int = Field(default=30, ge=1, description="Fast timeout for quick execution")
    # Hardware hints for Ollama configuration
    num_gpu: int = Field(
        default=1, ge=0, description="Number of GPU layers to use (0 for CPU-only)"
    )
    num_thread: int = Field(
        default=4, ge=1, description="Number of CPU threads for inference"
    )
    num_ctx: int = Field(default=4096, ge=1, description="Context window size")
    cpu_ram_gb: int = Field(
        default=16, ge=1, description="Recommended CPU RAM in GB (for resource planning)"
    )
    gpu_vram_gb: int = Field(
        default=8, ge=0, description="Recommended GPU VRAM in GB (0 if CPU-only)"
    )


class DualLLMConfig(BaseModel):
    """Configuration for dual-model setup (Brain + Executor)."""

    brain: BrainLLMConfig = Field(default_factory=BrainLLMConfig)
    executor: ExecutorLLMConfig = Field(default_factory=ExecutorLLMConfig)
    enabled: bool = Field(
        default=False,
        description="Enable dual-model mode (if False, falls back to single LLM config)",
    )


class SafetyConfig(BaseModel):
    """Configuration for safety features."""

    enable_input_validation: bool = Field(default=True)
    enable_output_filtering: bool = Field(default=True)
    max_command_length: int = Field(default=10000)


class StorageConfig(BaseModel):
    """Configuration for storage paths."""

    data_dir: Path = Field(default_factory=lambda: Path.home() / ".jarvis" / "data")
    logs_dir: Path = Field(default_factory=lambda: Path.home() / ".jarvis" / "logs")
    config_file: Path = Field(default_factory=lambda: Path.home() / ".jarvis" / "config.yaml")


class ExecutionConfig(BaseModel):
    """Configuration for action execution."""

    allowed_directories: Optional[list[str]] = Field(
        default=None, description="Directories where file operations are allowed"
    )
    disallowed_directories: Optional[list[str]] = Field(
        default=None, description="Directories where file operations are forbidden"
    )
    dry_run: bool = Field(default=False, description="Preview actions without executing")
    action_timeout: int = Field(default=30, ge=1, description="Timeout for actions in seconds")


class OCRConfig(BaseModel):
    """Configuration for OCR operations."""

    tesseract_path: Optional[str] = Field(
        default=None, description="Path to tesseract executable"
    )
    default_language: str = Field(default="eng", description="Default OCR language")
    confidence_threshold: float = Field(
        default=60.0, ge=0.0, le=100.0, description="OCR confidence threshold"
    )


class JarvisConfig(BaseModel):
    """Main Jarvis configuration."""

    llm: LLMConfig = Field(default_factory=LLMConfig)
    dual_llm: DualLLMConfig = Field(default_factory=DualLLMConfig)
    safety: SafetyConfig = Field(default_factory=SafetyConfig)
    storage: StorageConfig = Field(default_factory=StorageConfig)
    execution: ExecutionConfig = Field(default_factory=ExecutionConfig)
    ocr: OCRConfig = Field(default_factory=OCRConfig)
    debug: bool = Field(default=False, description="Enable debug logging")

    model_config = {"arbitrary_types_allowed": True}


class ConfigLoader:
    """Loads and manages configuration from various sources."""

    def __init__(self, config_path: Optional[Union[str, Path]] = None) -> None:
        """
        Initialize configuration loader.

        Args:
            config_path: Optional path to configuration file (YAML or JSON)
        """
        self.config_path = Path(config_path) if config_path else None
        self.config: Optional[JarvisConfig] = None

    def load(self) -> JarvisConfig:
        """
        Load configuration from file or return defaults.

        Returns:
            JarvisConfig: Loaded or default configuration

        Raises:
            FileNotFoundError: If config_path is specified but file doesn't exist
            ValueError: If file format is invalid
        """
        if self.config is not None:
            return self.config

        if self.config_path and self.config_path.exists():
            logger.info(f"Loading configuration from {self.config_path}")
            self.config = self._load_from_file(self.config_path)
        else:
            logger.info("Using default configuration")
            self.config = JarvisConfig()

        # Ensure storage directories exist
        self._ensure_directories()

        return self.config

    def _load_from_file(self, path: Path) -> JarvisConfig:
        """
        Load configuration from YAML or JSON file.

        Args:
            path: Path to configuration file

        Returns:
            JarvisConfig: Loaded configuration

        Raises:
            ValueError: If file format is unsupported
        """
        file_content = path.read_text()

        if path.suffix.lower() in {".yaml", ".yml"}:
            data = yaml.safe_load(file_content) or {}
        elif path.suffix.lower() == ".json":
            data = json.loads(file_content)
        else:
            raise ValueError(f"Unsupported config file format: {path.suffix}")

        logger.debug(f"Loaded config data: {data}")
        return JarvisConfig(**data)

    def _ensure_directories(self) -> None:
        """Create storage directories if they don't exist."""
        if self.config is None:
            return

        for dir_path in [self.config.storage.data_dir, self.config.storage.logs_dir]:
            dir_path.mkdir(parents=True, exist_ok=True)
            logger.debug(f"Ensured directory exists: {dir_path}")

    def get(self) -> JarvisConfig:
        """
        Get current configuration (loads if not already loaded).

        Returns:
            JarvisConfig: Current configuration
        """
        if self.config is None:
            self.load()
        return self.config

    def to_dict(self) -> Dict[str, Any]:
        """
        Convert configuration to dictionary.

        Returns:
            Dictionary representation of configuration
        """
        if self.config is None:
            self.load()
        config_dict = self.config.model_dump()
        # Convert Path objects to strings for YAML serialization
        return self._convert_paths_to_strings(config_dict)

    def _convert_paths_to_strings(self, obj: Any) -> Any:
        """
        Recursively convert Path objects to strings.

        Args:
            obj: Object to convert

        Returns:
            Object with Path objects converted to strings
        """
        if isinstance(obj, dict):
            return {key: self._convert_paths_to_strings(value) for key, value in obj.items()}
        elif isinstance(obj, (list, tuple)):
            return [self._convert_paths_to_strings(item) for item in obj]
        elif isinstance(obj, Path):
            return str(obj)
        return obj

    def to_yaml(self) -> str:
        """
        Convert configuration to YAML string.

        Returns:
            YAML string representation
        """
        if self.config is None:
            self.load()
        return yaml.dump(self.to_dict(), default_flow_style=False)
