"""
Action executor module for fast execution of identified actionable commands.

Provides real-time execution of file operations, application control, system info,
and web queries with structured results and optional progress streaming.
"""

import json
import logging
import os
import platform
import shutil
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Generator, List, Optional, Union

import requests  # type: ignore
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)


class ActionResult(BaseModel):
    """Structured result from an executed action."""

    success: bool = Field(description="Whether the action succeeded")
    action_type: str = Field(description="Type of action performed")
    message: str = Field(description="Human-readable result message")
    data: Optional[Dict[str, Any]] = Field(
        default=None, description="Additional structured data from the action"
    )
    error: Optional[str] = Field(default=None, description="Error message if action failed")
    execution_time_ms: float = Field(
        default=0.0, description="Time taken to execute in milliseconds"
    )

    model_config = {"arbitrary_types_allowed": True}


class ActionExecutor:
    """
    Executes identified actionable commands with safety guards and progress tracking.

    Supports file operations, application control, system info, and web queries.
    All operations are logged for auditing and include proper exception handling.
    """

    def __init__(
        self,
        allowed_directories: Optional[List[Union[str, Path]]] = None,
        disallowed_directories: Optional[List[Union[str, Path]]] = None,
        dry_run: bool = False,
        action_timeout: int = 30,
    ) -> None:
        """
        Initialize the action executor with safety configuration.

        Args:
            allowed_directories: List of directories where file operations are allowed
                (allowlist - if provided, only these dirs are accessible)
            disallowed_directories: List of directories where file operations are forbidden
                (denylist - takes precedence over allowlist)
            dry_run: If True, preview actions without executing
            action_timeout: Timeout in seconds for subprocess operations
        """
        self.allowed_directories = [
            Path(d).expanduser().resolve() for d in (allowed_directories or [])
        ]
        self.disallowed_directories = [
            Path(d).expanduser().resolve() for d in (disallowed_directories or [])
        ]
        self.dry_run = dry_run
        self.action_timeout = action_timeout

    def _check_path_allowed(self, path: Path) -> bool:
        """
        Check if a path is allowed for file operations.

        Args:
            path: Path to check

        Returns:
            True if path is allowed, False otherwise
        """
        path_resolved = path.expanduser().resolve()

        # Check disallowed directories first (takes precedence)
        for disallowed in self.disallowed_directories:
            try:
                path_resolved.relative_to(disallowed)
                logger.warning(f"Path {path_resolved} is in disallowed directory {disallowed}")
                return False
            except ValueError:
                pass

        # If allowlist is specified, check against it
        if self.allowed_directories:
            for allowed in self.allowed_directories:
                try:
                    path_resolved.relative_to(allowed)
                    return True
                except ValueError:
                    pass
            logger.warning(f"Path {path_resolved} is not in allowed directories")
            return False

        return True

    def list_files(self, directory: Union[str, Path], recursive: bool = False) -> ActionResult:
        """
        List files in a directory.

        Args:
            directory: Directory to list
            recursive: If True, recursively list subdirectories

        Returns:
            ActionResult with list of files
        """
        import time

        start_time = time.time()
        try:
            dir_path = Path(directory).expanduser().resolve()

            if not self._check_path_allowed(dir_path):
                return ActionResult(
                    success=False,
                    action_type="list_files",
                    message=f"Access denied to {directory}",
                    error="Path is not in allowed directories",
                    execution_time_ms=(time.time() - start_time) * 1000,
                )

            if not dir_path.exists():
                return ActionResult(
                    success=False,
                    action_type="list_files",
                    message=f"Directory does not exist: {directory}",
                    error=f"Directory not found: {dir_path}",
                    execution_time_ms=(time.time() - start_time) * 1000,
                )

            if not dir_path.is_dir():
                return ActionResult(
                    success=False,
                    action_type="list_files",
                    message=f"Not a directory: {directory}",
                    error=f"Path is not a directory: {dir_path}",
                    execution_time_ms=(time.time() - start_time) * 1000,
                )

            if recursive:
                files = [str(p.relative_to(dir_path)) for p in dir_path.rglob("*")]
            else:
                files = [str(p.relative_to(dir_path)) for p in dir_path.iterdir()]

            logger.info(f"Listed {len(files)} items in {dir_path}")
            return ActionResult(
                success=True,
                action_type="list_files",
                message=f"Listed {len(files)} items in {directory}",
                data={"files": sorted(files), "directory": str(dir_path)},
                execution_time_ms=(time.time() - start_time) * 1000,
            )

        except Exception as e:
            logger.error(f"Error listing files in {directory}: {e}")
            return ActionResult(
                success=False,
                action_type="list_files",
                message=f"Error listing directory: {str(e)}",
                error=str(e),
                execution_time_ms=(time.time() - start_time) * 1000,
            )

    def create_file(self, file_path: Union[str, Path], content: str = "") -> ActionResult:
        """
        Create a new file with optional content.

        Args:
            file_path: Path to file to create
            content: Initial content for the file

        Returns:
            ActionResult indicating success or failure
        """
        import time

        start_time = time.time()
        try:
            fpath = Path(file_path).expanduser().resolve()

            if not self._check_path_allowed(fpath):
                return ActionResult(
                    success=False,
                    action_type="create_file",
                    message=f"Access denied to {file_path}",
                    error="Path is not in allowed directories",
                    execution_time_ms=(time.time() - start_time) * 1000,
                )

            if fpath.exists():
                return ActionResult(
                    success=False,
                    action_type="create_file",
                    message=f"File already exists: {file_path}",
                    error=f"File exists: {fpath}",
                    execution_time_ms=(time.time() - start_time) * 1000,
                )

            fpath.parent.mkdir(parents=True, exist_ok=True)

            if self.dry_run:
                logger.info(f"[DRY RUN] Would create file: {fpath} with {len(content)} bytes")
                return ActionResult(
                    success=True,
                    action_type="create_file",
                    message=f"[DRY RUN] Would create file: {file_path}",
                    data={"file": str(fpath), "size_bytes": len(content)},
                    execution_time_ms=(time.time() - start_time) * 1000,
                )

            fpath.write_text(content)
            logger.info(f"Created file: {fpath} ({len(content)} bytes)")
            return ActionResult(
                success=True,
                action_type="create_file",
                message=f"Created file: {file_path}",
                data={"file": str(fpath), "size_bytes": len(content)},
                execution_time_ms=(time.time() - start_time) * 1000,
            )

        except Exception as e:
            logger.error(f"Error creating file {file_path}: {e}")
            return ActionResult(
                success=False,
                action_type="create_file",
                message=f"Error creating file: {str(e)}",
                error=str(e),
                execution_time_ms=(time.time() - start_time) * 1000,
            )

    def delete_file(self, file_path: Union[str, Path]) -> ActionResult:
        """
        Delete a file with safety checks.

        Args:
            file_path: Path to file to delete

        Returns:
            ActionResult indicating success or failure
        """
        import time

        start_time = time.time()
        try:
            fpath = Path(file_path).expanduser().resolve()

            if not self._check_path_allowed(fpath):
                return ActionResult(
                    success=False,
                    action_type="delete_file",
                    message=f"Access denied to {file_path}",
                    error="Path is not in allowed directories",
                    execution_time_ms=(time.time() - start_time) * 1000,
                )

            if not fpath.exists():
                return ActionResult(
                    success=False,
                    action_type="delete_file",
                    message=f"File not found: {file_path}",
                    error=f"File does not exist: {fpath}",
                    execution_time_ms=(time.time() - start_time) * 1000,
                )

            if fpath.is_dir():
                return ActionResult(
                    success=False,
                    action_type="delete_file",
                    message=f"Cannot delete directory: {file_path}",
                    error="Use delete_directory for directories",
                    execution_time_ms=(time.time() - start_time) * 1000,
                )

            if self.dry_run:
                logger.info(f"[DRY RUN] Would delete file: {fpath}")
                return ActionResult(
                    success=True,
                    action_type="delete_file",
                    message=f"[DRY RUN] Would delete file: {file_path}",
                    data={"file": str(fpath)},
                    execution_time_ms=(time.time() - start_time) * 1000,
                )

            fpath.unlink()
            logger.info(f"Deleted file: {fpath}")
            return ActionResult(
                success=True,
                action_type="delete_file",
                message=f"Deleted file: {file_path}",
                data={"file": str(fpath)},
                execution_time_ms=(time.time() - start_time) * 1000,
            )

        except Exception as e:
            logger.error(f"Error deleting file {file_path}: {e}")
            return ActionResult(
                success=False,
                action_type="delete_file",
                message=f"Error deleting file: {str(e)}",
                error=str(e),
                execution_time_ms=(time.time() - start_time) * 1000,
            )

    def delete_directory(self, directory: Union[str, Path]) -> ActionResult:
        """
        Delete a directory recursively with safety checks.

        Args:
            directory: Directory to delete

        Returns:
            ActionResult indicating success or failure
        """
        import time

        start_time = time.time()
        try:
            dir_path = Path(directory).expanduser().resolve()

            if not self._check_path_allowed(dir_path):
                return ActionResult(
                    success=False,
                    action_type="delete_directory",
                    message=f"Access denied to {directory}",
                    error="Path is not in allowed directories",
                    execution_time_ms=(time.time() - start_time) * 1000,
                )

            if not dir_path.exists():
                return ActionResult(
                    success=False,
                    action_type="delete_directory",
                    message=f"Directory not found: {directory}",
                    error=f"Directory does not exist: {dir_path}",
                    execution_time_ms=(time.time() - start_time) * 1000,
                )

            if not dir_path.is_dir():
                return ActionResult(
                    success=False,
                    action_type="delete_directory",
                    message=f"Not a directory: {directory}",
                    error=f"Path is not a directory: {dir_path}",
                    execution_time_ms=(time.time() - start_time) * 1000,
                )

            if self.dry_run:
                logger.info(f"[DRY RUN] Would delete directory: {dir_path}")
                return ActionResult(
                    success=True,
                    action_type="delete_directory",
                    message=f"[DRY RUN] Would delete directory: {directory}",
                    data={"directory": str(dir_path)},
                    execution_time_ms=(time.time() - start_time) * 1000,
                )

            shutil.rmtree(dir_path)
            logger.info(f"Deleted directory: {dir_path}")
            return ActionResult(
                success=True,
                action_type="delete_directory",
                message=f"Deleted directory: {directory}",
                data={"directory": str(dir_path)},
                execution_time_ms=(time.time() - start_time) * 1000,
            )

        except Exception as e:
            logger.error(f"Error deleting directory {directory}: {e}")
            return ActionResult(
                success=False,
                action_type="delete_directory",
                message=f"Error deleting directory: {str(e)}",
                error=str(e),
                execution_time_ms=(time.time() - start_time) * 1000,
            )

    def move_file(self, source: Union[str, Path], destination: Union[str, Path]) -> ActionResult:
        """
        Move or rename a file.

        Args:
            source: Source file path
            destination: Destination file path

        Returns:
            ActionResult indicating success or failure
        """
        import time

        start_time = time.time()
        try:
            src_path = Path(source).expanduser().resolve()
            dst_path = Path(destination).expanduser().resolve()

            if not self._check_path_allowed(src_path):
                return ActionResult(
                    success=False,
                    action_type="move_file",
                    message=f"Access denied to source: {source}",
                    error="Source path is not in allowed directories",
                    execution_time_ms=(time.time() - start_time) * 1000,
                )

            if not self._check_path_allowed(dst_path):
                return ActionResult(
                    success=False,
                    action_type="move_file",
                    message=f"Access denied to destination: {destination}",
                    error="Destination path is not in allowed directories",
                    execution_time_ms=(time.time() - start_time) * 1000,
                )

            if not src_path.exists():
                return ActionResult(
                    success=False,
                    action_type="move_file",
                    message=f"Source file not found: {source}",
                    error=f"Source does not exist: {src_path}",
                    execution_time_ms=(time.time() - start_time) * 1000,
                )

            if dst_path.exists():
                return ActionResult(
                    success=False,
                    action_type="move_file",
                    message=f"Destination already exists: {destination}",
                    error=f"Destination exists: {dst_path}",
                    execution_time_ms=(time.time() - start_time) * 1000,
                )

            dst_path.parent.mkdir(parents=True, exist_ok=True)

            if self.dry_run:
                logger.info(f"[DRY RUN] Would move {src_path} to {dst_path}")
                return ActionResult(
                    success=True,
                    action_type="move_file",
                    message=f"[DRY RUN] Would move {source} to {destination}",
                    data={"source": str(src_path), "destination": str(dst_path)},
                    execution_time_ms=(time.time() - start_time) * 1000,
                )

            src_path.rename(dst_path)
            logger.info(f"Moved {src_path} to {dst_path}")
            return ActionResult(
                success=True,
                action_type="move_file",
                message=f"Moved file from {source} to {destination}",
                data={"source": str(src_path), "destination": str(dst_path)},
                execution_time_ms=(time.time() - start_time) * 1000,
            )

        except Exception as e:
            logger.error(f"Error moving file from {source} to {destination}: {e}")
            return ActionResult(
                success=False,
                action_type="move_file",
                message=f"Error moving file: {str(e)}",
                error=str(e),
                execution_time_ms=(time.time() - start_time) * 1000,
            )

    def copy_file(self, source: Union[str, Path], destination: Union[str, Path]) -> ActionResult:
        """
        Copy a file.

        Args:
            source: Source file path
            destination: Destination file path

        Returns:
            ActionResult indicating success or failure
        """
        import time

        start_time = time.time()
        try:
            src_path = Path(source).expanduser().resolve()
            dst_path = Path(destination).expanduser().resolve()

            if not self._check_path_allowed(src_path):
                return ActionResult(
                    success=False,
                    action_type="copy_file",
                    message=f"Access denied to source: {source}",
                    error="Source path is not in allowed directories",
                    execution_time_ms=(time.time() - start_time) * 1000,
                )

            if not self._check_path_allowed(dst_path):
                return ActionResult(
                    success=False,
                    action_type="copy_file",
                    message=f"Access denied to destination: {destination}",
                    error="Destination path is not in allowed directories",
                    execution_time_ms=(time.time() - start_time) * 1000,
                )

            if not src_path.exists():
                return ActionResult(
                    success=False,
                    action_type="copy_file",
                    message=f"Source file not found: {source}",
                    error=f"Source does not exist: {src_path}",
                    execution_time_ms=(time.time() - start_time) * 1000,
                )

            if dst_path.exists():
                return ActionResult(
                    success=False,
                    action_type="copy_file",
                    message=f"Destination already exists: {destination}",
                    error=f"Destination exists: {dst_path}",
                    execution_time_ms=(time.time() - start_time) * 1000,
                )

            dst_path.parent.mkdir(parents=True, exist_ok=True)

            if self.dry_run:
                logger.info(f"[DRY RUN] Would copy {src_path} to {dst_path}")
                return ActionResult(
                    success=True,
                    action_type="copy_file",
                    message=f"[DRY RUN] Would copy {source} to {destination}",
                    data={"source": str(src_path), "destination": str(dst_path)},
                    execution_time_ms=(time.time() - start_time) * 1000,
                )

            shutil.copy2(src_path, dst_path)
            logger.info(f"Copied {src_path} to {dst_path}")
            return ActionResult(
                success=True,
                action_type="copy_file",
                message=f"Copied file from {source} to {destination}",
                data={"source": str(src_path), "destination": str(dst_path)},
                execution_time_ms=(time.time() - start_time) * 1000,
            )

        except Exception as e:
            logger.error(f"Error copying file from {source} to {destination}: {e}")
            return ActionResult(
                success=False,
                action_type="copy_file",
                message=f"Error copying file: {str(e)}",
                error=str(e),
                execution_time_ms=(time.time() - start_time) * 1000,
            )

    def open_application(self, app_path: Union[str, Path]) -> ActionResult:
        """
        Open an application or file with its default handler.

        Args:
            app_path: Path to application or file to open

        Returns:
            ActionResult indicating success or failure
        """
        import time

        start_time = time.time()
        try:
            path_to_open = Path(app_path).expanduser().resolve()

            if not path_to_open.exists():
                return ActionResult(
                    success=False,
                    action_type="open_application",
                    message=f"Application or file not found: {app_path}",
                    error=f"Path does not exist: {path_to_open}",
                    execution_time_ms=(time.time() - start_time) * 1000,
                )

            if self.dry_run:
                logger.info(f"[DRY RUN] Would open: {path_to_open}")
                return ActionResult(
                    success=True,
                    action_type="open_application",
                    message=f"[DRY RUN] Would open: {app_path}",
                    data={"path": str(path_to_open)},
                    execution_time_ms=(time.time() - start_time) * 1000,
                )

            if sys.platform == "win32":
                os.startfile(str(path_to_open))
            elif sys.platform == "darwin":
                subprocess.run(
                    ["open", str(path_to_open)],
                    check=True,
                    timeout=self.action_timeout,
                    stdin=subprocess.DEVNULL,
                )
            else:
                subprocess.run(
                    ["xdg-open", str(path_to_open)],
                    check=True,
                    timeout=self.action_timeout,
                    stdin=subprocess.DEVNULL,
                )

            logger.info(f"Opened: {path_to_open}")
            return ActionResult(
                success=True,
                action_type="open_application",
                message=f"Opened: {app_path}",
                data={"path": str(path_to_open)},
                execution_time_ms=(time.time() - start_time) * 1000,
            )

        except subprocess.TimeoutExpired:
            logger.error(f"Timeout opening {app_path}")
            return ActionResult(
                success=False,
                action_type="open_application",
                message=f"Timeout opening application: {app_path}",
                error=f"Operation timed out after {self.action_timeout}s",
                execution_time_ms=(time.time() - start_time) * 1000,
            )
        except Exception as e:
            logger.error(f"Error opening {app_path}: {e}")
            return ActionResult(
                success=False,
                action_type="open_application",
                message=f"Error opening application: {str(e)}",
                error=str(e),
                execution_time_ms=(time.time() - start_time) * 1000,
            )

    def get_system_info(self) -> ActionResult:
        """
        Get system information (time, date, OS stats).

        Returns:
            ActionResult with system info
        """
        import time

        start_time = time.time()
        try:
            now = datetime.now()
            info = {
                "timestamp": now.isoformat(),
                "date": now.strftime("%Y-%m-%d"),
                "time": now.strftime("%H:%M:%S"),
                "timezone": datetime.now().astimezone().tzname(),
                "platform": platform.system(),
                "platform_release": platform.release(),
                "platform_version": platform.version(),
                "architecture": platform.machine(),
                "processor": platform.processor(),
                "python_version": platform.python_version(),
            }

            logger.info("Retrieved system info")
            return ActionResult(
                success=True,
                action_type="get_system_info",
                message="System information retrieved",
                data=info,
                execution_time_ms=(time.time() - start_time) * 1000,
            )

        except Exception as e:
            logger.error(f"Error getting system info: {e}")
            return ActionResult(
                success=False,
                action_type="get_system_info",
                message=f"Error getting system info: {str(e)}",
                error=str(e),
                execution_time_ms=(time.time() - start_time) * 1000,
            )

    def get_weather(self, location: str = "auto", timeout: int = 10) -> ActionResult:
        """
        Get weather information from wttr.in service.

        Args:
            location: Location to get weather for (default: auto-detect)
            timeout: Request timeout in seconds

        Returns:
            ActionResult with weather info
        """
        import time

        start_time = time.time()
        try:
            # Use wttr.in API for simple weather lookup
            url = "https://wttr.in/{location}?format=j1".format(location=location)
            response = requests.get(url, timeout=timeout)
            response.raise_for_status()

            data = response.json()
            current = data.get("current_condition", [{}])[0]

            weather_info = {
                "location": location if location != "auto" else "Current Location",
                "temperature": f"{current.get('temp_C', 'N/A')}°C",
                "condition": current.get("weatherDesc", [{}])[0].get("value", "N/A"),
                "humidity": f"{current.get('humidity', 'N/A')}%",
                "wind_speed": f"{current.get('windspeedKmph', 'N/A')} km/h",
                "feels_like": f"{current.get('FeelsLikeC', 'N/A')}°C",
                "uv_index": current.get("uvIndex", "N/A"),
            }

            logger.info(f"Retrieved weather for {location}")
            return ActionResult(
                success=True,
                action_type="get_weather",
                message=f"Weather retrieved for {location}",
                data=weather_info,
                execution_time_ms=(time.time() - start_time) * 1000,
            )

        except requests.RequestException as e:
            logger.error(f"Error fetching weather for {location}: {e}")
            return ActionResult(
                success=False,
                action_type="get_weather",
                message=f"Error fetching weather: {str(e)}",
                error=str(e),
                execution_time_ms=(time.time() - start_time) * 1000,
            )
        except (KeyError, json.JSONDecodeError) as e:
            logger.error(f"Error parsing weather response: {e}")
            return ActionResult(
                success=False,
                action_type="get_weather",
                message=f"Error parsing weather data: {str(e)}",
                error=str(e),
                execution_time_ms=(time.time() - start_time) * 1000,
            )

    def execute_command_stream(
        self, command: str, shell: bool = True, timeout: Optional[int] = None
    ) -> Generator[str, None, ActionResult]:
        """
        Execute a shell command with streaming output.

        Uses subprocess.run() for Windows compatibility, avoiding WinError 10038.

        Args:
            command: Command to execute
            shell: If True, execute through shell
            timeout: Timeout in seconds

        Yields:
            Status messages and output

        Returns:
            Final ActionResult with execution details
        """
        import sys
        import time

        start_time = time.time()
        timeout = timeout or self.action_timeout

        try:
            if self.dry_run:
                yield f"[DRY RUN] Would execute: {command}\n"
                yield "[DRY RUN] Command execution skipped in dry-run mode\n"
                result = ActionResult(
                    success=True,
                    action_type="execute_command",
                    message=f"[DRY RUN] Would execute: {command}",
                    data={"command": command, "output": ""},
                    execution_time_ms=(time.time() - start_time) * 1000,
                )
                return result

            yield f"Executing: {command}\n"

            creation_flags = 0
            if sys.platform == "win32":
                creation_flags = subprocess.CREATE_NEW_PROCESS_GROUP

            # Use subprocess.run() instead of Popen for better Windows compatibility
            process = subprocess.run(
                command,
                shell=shell,
                capture_output=True,
                text=True,
                timeout=timeout,
                creationflags=creation_flags,
            )

            # Yield stdout line by line
            if process.stdout:
                for line in process.stdout.splitlines(keepends=True):
                    yield line

            # Yield stderr line by line
            if process.stderr:
                for line in process.stderr.splitlines(keepends=True):
                    yield f"[stderr] {line}"

            exit_code = process.returncode
            stdout_str = process.stdout if process.stdout else ""
            stderr_str = process.stderr if process.stderr else ""

            if exit_code == 0:
                result = ActionResult(
                    success=True,
                    action_type="execute_command",
                    message="Command executed successfully",
                    data={
                        "command": command,
                        "exit_code": exit_code,
                        "output": stdout_str,
                    },
                    execution_time_ms=(time.time() - start_time) * 1000,
                )
            else:
                result = ActionResult(
                    success=False,
                    action_type="execute_command",
                    message=f"Command failed with exit code {exit_code}",
                    error=stderr_str or "Unknown error",
                    data={
                        "command": command,
                        "exit_code": exit_code,
                        "output": stdout_str,
                    },
                    execution_time_ms=(time.time() - start_time) * 1000,
                )

            logger.info("Command executed: %s (exit code: %s)", command, exit_code)
            return result

        except subprocess.TimeoutExpired:
            logger.error(f"Command timed out: {command}")
            yield f"[ERROR] Command timed out after {timeout}s\n"
            result = ActionResult(
                success=False,
                action_type="execute_command",
                message=f"Command timed out after {timeout}s",
                error=f"Execution exceeded {timeout}s timeout",
                data={"command": command},
                execution_time_ms=(time.time() - start_time) * 1000,
            )
            return result

        except Exception as e:
            logger.error(f"Error executing command: {e}")
            yield f"[ERROR] {str(e)}\n"
            result = ActionResult(
                success=False,
                action_type="execute_command",
                message=f"Error executing command: {str(e)}",
                error=str(e),
                data={"command": command},
                execution_time_ms=(time.time() - start_time) * 1000,
            )
            return result
