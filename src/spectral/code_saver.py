"""
Code Saver module for persistent storage of all generated code.

Every code generation (successful or failed) is saved to Desktop/spectral/
with metadata, partial chunks, and final code.
"""

import json
import logging
import threading
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)


@dataclass
class GenerationRecord:
    """Record of a code generation."""
    request_id: str
    prompt: str
    attempt_number: int
    timestamp: str
    status: str
    error_message: Optional[str]
    sandbox_result: Optional[Dict]
    file_path: str
    code_length: int
    duration_seconds: float


@dataclass
class CodeSaveContext:
    """Context for saving code during a generation request."""
    request_id: str
    prompt: str
    attempt_number: int
    date_dir: Path
    request_dir: Path
    attempt_dir: Path
    code_file: Path
    partial_log_file: Path
    metadata_file: Path
    final_dir: Optional[Path]
    start_time: float
    accumulated_code: str
    lock: threading.Lock

    def __post_init__(self):
        """Initialize lock and accumulated code."""
        if self.accumulated_code is None:
            self.accumulated_code = ""
        if self.lock is None:
            self.lock = threading.Lock()


class CodeSaver:
    """
    Manages persistent storage of all generated code.

    Features:
    - Desktop/spectral/ directory structure
    - Organized by date, request, and attempt
    - Saves partial chunks as code is generated
    - Maintains MANIFEST.json index
    - Thread-safe for concurrent operations
    """

    def __init__(self, base_path: Optional[Path] = None):
        """
        Initialize code saver.

        Args:
            base_path: Base path for code storage (defaults to Desktop/spectral/)
        """
        if base_path is None:
            base_path = Path.home() / "Desktop" / "spectral"

        self.base_path = base_path
        self.base_path.mkdir(parents=True, exist_ok=True)

        # Ensure MANIFEST.json exists
        self.manifest_path = self.base_path / "MANIFEST.json"
        self._init_manifest()

        logger.info(f"CodeSaver initialized with base_path: {self.base_path}")

    def _init_manifest(self) -> None:
        """Initialize MANIFEST.json if it doesn't exist."""
        if not self.manifest_path.exists():
            self.manifest_path.write_text(json.dumps({
                "version": "1.0",
                "created": datetime.now(timezone.utc).isoformat(),
                "generations": []
            }, indent=2))

    def _get_date_dir(self) -> Path:
        """Get or create today's date directory."""
        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        date_dir = self.base_path / today
        date_dir.mkdir(exist_ok=True)
        return date_dir

    def _generate_request_id(self, prompt: str) -> str:
        """Generate a unique request ID based on prompt."""
        # Extract key words from prompt
        import re
        words = re.findall(r"[a-z0-9]+", prompt.lower())
        meaningful_words = [w for w in words if len(w) > 2][:5]

        if meaningful_words:
            name_part = "_".join(meaningful_words)
        else:
            name_part = "request"

        # Add sequential number
        date_dir = self._get_date_dir()
        existing_requests = [d.name for d in date_dir.iterdir() if d.is_dir()]

        # Find the next number
        max_num = 0
        for req_dir in existing_requests:
            match = re.match(rf"{re.escape(name_part)}_(\d+)", req_dir)
            if match:
                num = int(match.group(1))
                max_num = max(max_num, num)

        next_num = max_num + 1
        return f"{name_part}_{next_num:03d}"

    def create_request(
        self,
        prompt: str,
        request_id: Optional[str] = None
    ) -> CodeSaveContext:
        """
        Create a new request folder and return context for saving.

        Args:
            prompt: User's original prompt
            request_id: Optional request ID (auto-generated if not provided)

        Returns:
            CodeSaveContext with paths for saving code
        """
        if request_id is None:
            request_id = self._generate_request_id(prompt)

        date_dir = self._get_date_dir()
        request_dir = date_dir / request_id
        request_dir.mkdir(exist_ok=True)

        # Create attempt_1 directory
        attempt_number = 1
        attempt_dir = request_dir / f"attempt_{attempt_number}"
        attempt_dir.mkdir(exist_ok=True)

        # Define file paths
        code_file = attempt_dir / "generated.py"
        partial_log_file = attempt_dir / "partial_code_log.txt"
        metadata_file = attempt_dir / "metadata.json"

        # Create context
        context = CodeSaveContext(
            request_id=request_id,
            prompt=prompt,
            attempt_number=attempt_number,
            date_dir=date_dir,
            request_dir=request_dir,
            attempt_dir=attempt_dir,
            code_file=code_file,
            partial_log_file=partial_log_file,
            metadata_file=metadata_file,
            final_dir=None,
            start_time=time.time(),
            accumulated_code="",
            lock=threading.Lock()
        )

        # Write initial metadata with "partial" status
        self._write_metadata(context, "partial", None, None)

        logger.info(f"Created request context: {request_id} at {attempt_dir}")
        return context

    def create_retry_attempt(self, context: CodeSaveContext) -> CodeSaveContext:
        """
        Create a new attempt directory for a retry.

        Args:
            context: Previous CodeSaveContext

        Returns:
            New CodeSaveContext for the retry attempt
        """
        new_attempt_number = context.attempt_number + 1
        new_attempt_dir = context.request_dir / f"attempt_{new_attempt_number}"
        new_attempt_dir.mkdir(exist_ok=True)

        # Define new file paths
        code_file = new_attempt_dir / "generated.py"
        partial_log_file = new_attempt_dir / "partial_code_log.txt"
        metadata_file = new_attempt_dir / "metadata.json"

        # Create new context
        new_context = CodeSaveContext(
            request_id=context.request_id,
            prompt=context.prompt,
            attempt_number=new_attempt_number,
            date_dir=context.date_dir,
            request_dir=context.request_dir,
            attempt_dir=new_attempt_dir,
            code_file=code_file,
            partial_log_file=partial_log_file,
            metadata_file=metadata_file,
            final_dir=None,
            start_time=time.time(),
            accumulated_code="",
            lock=threading.Lock()
        )

        # Write initial metadata
        self._write_metadata(new_context, "partial", None, None)

        logger.info(f"Created retry attempt {new_attempt_number} for request {context.request_id}")
        return new_context

    def save_partial_code(self, context: CodeSaveContext, code_chunk: str) -> None:
        """
        Save a chunk of code as it's being generated (streaming).

        Args:
            context: CodeSaveContext for this generation
            code_chunk: Chunk of code to save
        """
        with context.lock:
            context.accumulated_code += code_chunk

            # Write to generated.py (latest state)
            try:
                context.code_file.write_text(context.accumulated_code)
            except Exception as e:
                logger.error(f"Failed to write code file: {e}")

            # Append to partial log
            try:
                with open(context.partial_log_file, "a", encoding="utf-8") as f:
                    f.write(f"[{datetime.now(timezone.utc).isoformat()}] CHUNK:\n")
                    f.write(code_chunk)
                    f.write("\n" + "="*50 + "\n")
            except Exception as e:
                logger.error(f"Failed to write partial log: {e}")

    def save_final_code(
        self,
        context: CodeSaveContext,
        final_code: str,
        status: str,
        sandbox_result: Optional[Dict] = None,
        error_message: Optional[str] = None
    ) -> Path:
        """
        Save final code and mark attempt as complete.

        Args:
            context: CodeSaveContext for this generation
            final_code: Final generated code
            status: Status ("success", "failed", "partial")
            sandbox_result: Optional sandbox verification result
            error_message: Optional error message if failed

        Returns:
            Path to the saved file
        """
        duration = time.time() - context.start_time

        with context.lock:
            context.accumulated_code = final_code

            # Write final code
            context.code_file.write_text(final_code)

            # Write metadata
            self._write_metadata(
                context, status, error_message, sandbox_result, duration
            )

            # If successful, also save to FINAL/ directory
            if status == "success":
                final_dir = context.request_dir / "FINAL"
                final_dir.mkdir(exist_ok=True)

                final_code_file = final_dir / "generated.py"
                final_code_file.write_text(final_code)

                final_metadata_file = final_dir / "metadata.json"
                final_metadata_file.write_text(json.dumps({
                    "request_id": context.request_id,
                    "prompt": context.prompt,
                    "successful_attempt": context.attempt_number,
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                    "status": "success",
                    "sandbox_result": sandbox_result,
                    "file_path": str(final_code_file),
                    "code_length": len(final_code),
                    "duration_seconds": duration
                }, indent=2))

                context.final_dir = final_dir

                # Update MANIFEST.json
                self.update_manifest(
                    context, status, sandbox_result, error_message, duration
                )

                logger.info(
                    f"Saved final code for {context.request_id} "
                    f"attempt {context.attempt_number}"
                )

        return context.code_file

    def _write_metadata(
        self,
        context: CodeSaveContext,
        status: str,
        error_message: Optional[str],
        sandbox_result: Optional[Dict],
        duration: Optional[float] = None
    ) -> None:
        """
        Write metadata.json for an attempt.

        Args:
            context: CodeSaveContext
            status: Status string
            error_message: Optional error message
            sandbox_result: Optional sandbox result
            duration: Optional duration in seconds
        """
        if duration is None:
            duration = time.time() - context.start_time

        metadata = {
            "request_id": context.request_id,
            "prompt": context.prompt,
            "attempt_number": context.attempt_number,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "status": status,
        }

        if error_message:
            metadata["error_message"] = error_message

        if sandbox_result:
            metadata["sandbox_result"] = sandbox_result

        if context.accumulated_code:
            metadata["code_length"] = len(context.accumulated_code)

        metadata["duration_seconds"] = duration
        metadata["file_path"] = str(context.code_file)

        try:
            context.metadata_file.write_text(json.dumps(metadata, indent=2))
        except Exception as e:
            logger.error(f"Failed to write metadata: {e}")

    def update_manifest(
        self,
        context: CodeSaveContext,
        status: str,
        sandbox_result: Optional[Dict],
        error_message: Optional[str],
        duration: float
    ) -> None:
        """
        Update Desktop/spectral/MANIFEST.json with generation record.

        Args:
            context: CodeSaveContext
            status: Status string
            sandbox_result: Optional sandbox result
            error_message: Optional error message
            duration: Duration in seconds
        """
        try:
            # Read existing manifest
            manifest_data = json.loads(self.manifest_path.read_text())

            # Create record
            record = {
                "request_id": context.request_id,
                "prompt": context.prompt,
                "attempt_number": context.attempt_number,
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "status": status,
                "file_path": str(context.code_file),
                "code_length": len(context.accumulated_code),
                "duration_seconds": duration
            }

            if error_message:
                record["error_message"] = error_message

            if sandbox_result:
                record["sandbox_result"] = sandbox_result

            # Add to generations list
            manifest_data["generations"].append(record)
            manifest_data["last_updated"] = datetime.now(timezone.utc).isoformat()

            # Write back
            self.manifest_path.write_text(json.dumps(manifest_data, indent=2))

        except Exception as e:
            logger.error(f"Failed to update manifest: {e}")

    def get_all_generations(self) -> List[GenerationRecord]:
        """
        Return all saved code generations from MANIFEST.json.

        Returns:
            List of GenerationRecord objects
        """
        try:
            manifest_data = json.loads(self.manifest_path.read_text())
            records = []

            for gen_data in manifest_data.get("generations", []):
                record = GenerationRecord(
                    request_id=gen_data.get("request_id", ""),
                    prompt=gen_data.get("prompt", ""),
                    attempt_number=gen_data.get("attempt_number", 0),
                    timestamp=gen_data.get("timestamp", ""),
                    status=gen_data.get("status", ""),
                    error_message=gen_data.get("error_message"),
                    sandbox_result=gen_data.get("sandbox_result"),
                    file_path=gen_data.get("file_path", ""),
                    code_length=gen_data.get("code_length", 0),
                    duration_seconds=gen_data.get("duration_seconds", 0)
                )
                records.append(record)

            return records

        except Exception as e:
            logger.error(f"Failed to read generations: {e}")
            return []

    def get_generation_by_request_id(self, request_id: str) -> List[GenerationRecord]:
        """
        Get all attempts for a specific request ID.

        Args:
            request_id: Request ID to look up

        Returns:
            List of GenerationRecord objects for this request
        """
        all_generations = self.get_all_generations()
        return [g for g in all_generations if g.request_id == request_id]
