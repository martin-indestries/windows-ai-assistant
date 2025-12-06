"""
File operations system action module.

Delegates to ActionExecutor for file operations while enforcing
allow/deny lists and dry-run semantics.
"""

import logging
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

from jarvis.action_executor import ActionExecutor, ActionResult

logger = logging.getLogger(__name__)


class FileActions:
    """
    File operations system actions.

    Wraps ActionExecutor file operations with additional logging
    and standardized interface for the system action router.
    """

    def __init__(self, action_executor: ActionExecutor) -> None:
        """
        Initialize file actions with an ActionExecutor instance.

        Args:
            action_executor: Configured ActionExecutor instance
        """
        self.action_executor = action_executor
        logger.info("FileActions initialized")

    def _create_result(self, success: bool, action_type: str, message: str, 
                     data: Optional[Dict[str, Any]] = None, error: Optional[str] = None,
                     start_time: Optional[float] = None) -> ActionResult:
        """Create ActionResult with execution time."""
        execution_time = 0.0
        if start_time is not None:
            execution_time = (time.time() - start_time) * 1000  # Convert to ms
        
        return ActionResult(
            success=success,
            action_type=action_type,
            message=message,
            data=data,
            error=error,
            execution_time_ms=execution_time
        )

    def list_files(
        self, directory: Union[str, Path], recursive: bool = False
    ) -> ActionResult:
        """
        List files in a directory.

        Args:
            directory: Directory path to list
            recursive: Whether to list recursively

        Returns:
            ActionResult with file list or error
        """
        start_time = time.time()
        logger.info(f"Listing files in {directory} (recursive={recursive})")
        return self.action_executor.list_files(directory, recursive)

    def create_file(
        self, file_path: Union[str, Path], content: str = ""
    ) -> ActionResult:
        """
        Create a file with optional content.

        Args:
            file_path: Path to the file to create
            content: Optional content to write to the file

        Returns:
            ActionResult indicating success or failure
        """
        logger.info(f"Creating file {file_path}")
        return self.action_executor.create_file(file_path, content)

    def delete_file(self, file_path: Union[str, Path]) -> ActionResult:
        """
        Delete a file.

        Args:
            file_path: Path to the file to delete

        Returns:
            ActionResult indicating success or failure
        """
        logger.info(f"Deleting file {file_path}")
        return self.action_executor.delete_file(file_path)

    def delete_directory(self, directory: Union[str, Path]) -> ActionResult:
        """
        Delete a directory and its contents.

        Args:
            directory: Directory path to delete

        Returns:
            ActionResult indicating success or failure
        """
        logger.info(f"Deleting directory {directory}")
        return self.action_executor.delete_directory(directory)

    def move_file(
        self, source: Union[str, Path], destination: Union[str, Path]
    ) -> ActionResult:
        """
        Move or rename a file.

        Args:
            source: Source file path
            destination: Destination file path

        Returns:
            ActionResult indicating success or failure
        """
        logger.info(f"Moving file {source} to {destination}")
        return self.action_executor.move_file(source, destination)

    def copy_file(
        self, source: Union[str, Path], destination: Union[str, Path]
    ) -> ActionResult:
        """
        Copy a file.

        Args:
            source: Source file path
            destination: Destination file path

        Returns:
            ActionResult indicating success or failure
        """
        logger.info(f"Copying file {source} to {destination}")
        return self.action_executor.copy_file(source, destination)

    def get_file_info(self, file_path: Union[str, Path]) -> ActionResult:
        """
        Get information about a file.

        Args:
            file_path: Path to the file

        Returns:
            ActionResult with file information
        """
        logger.info(f"Getting file info for {file_path}")
        try:
            path = Path(file_path).expanduser().resolve()
            
            if not self.action_executor._check_path_allowed(path):
                return ActionResult(
                    success=False,
                    action_type="get_file_info",
                    message=f"Path {file_path} is not allowed",
                    error="Path access denied by safety rules"
                )

            if not path.exists():
                return ActionResult(
                    success=False,
                    action_type="get_file_info",
                    message=f"File {file_path} does not exist",
                    error="File not found"
                )

            stat = path.stat()
            info = {
                "path": str(path),
                "name": path.name,
                "size": stat.st_size,
                "modified": stat.st_mtime,
                "is_file": path.is_file(),
                "is_directory": path.is_dir(),
                "extension": path.suffix if path.is_file() else None,
            }

            return ActionResult(
                success=True,
                action_type="get_file_info",
                message=f"Retrieved info for {file_path}",
                data=info
            )

        except Exception as e:
            logger.error(f"Error getting file info for {file_path}: {e}")
            return ActionResult(
                success=False,
                action_type="get_file_info",
                message=f"Failed to get info for {file_path}",
                error=str(e)
            )