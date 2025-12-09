"""
Step verification module for the controller.

Inspects action results and confirms side effects to ensure actions
actually completed successfully (e.g., files exist after creation,
registry values match after writes, etc.).
"""

import logging
from pathlib import Path
from typing import Any, Dict, Optional

from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)


class VerificationResult(BaseModel):
    """Result of verifying an action's side effects."""

    verified: bool = Field(description="Whether the verification passed")
    action_type: str = Field(description="Type of action that was verified")
    message: str = Field(description="Human-readable verification message")
    details: Optional[Dict[str, Any]] = Field(
        default=None, description="Additional verification details"
    )
    error: Optional[str] = Field(default=None, description="Error message if verification failed")

    model_config = {"arbitrary_types_allowed": True}


class StepVerifier:
    """
    Verifier that inspects action results and confirms side effects.

    For actions that modify system state (file creation, deletion, registry
    writes, etc.), this verifier checks that the intended side effects
    actually occurred.
    """

    def __init__(self) -> None:
        """Initialize the step verifier."""
        logger.info("StepVerifier initialized")

    def verify(
        self,
        action_type: str,
        result_data: Optional[Dict[str, Any]],
        action_params: Optional[Dict[str, Any]] = None,
    ) -> VerificationResult:
        """
        Verify that an action's side effects occurred.

        Args:
            action_type: Type of action performed
            result_data: Data returned from the action execution
            action_params: Original parameters passed to the action

        Returns:
            VerificationResult indicating if verification passed
        """
        logger.debug(f"Verifying action: {action_type}")
        logger.debug(f"Result data: {result_data}")
        logger.debug(f"Action params: {action_params}")

        action_params = action_params or {}
        result_data = result_data or {}

        # Route to appropriate verification method
        if action_type in ("create_file", "file_create"):
            return self._verify_file_created(result_data, action_params)
        elif action_type in ("create_directory",):
            return self._verify_directory_created(result_data, action_params)
        elif action_type in ("delete_file", "file_delete"):
            return self._verify_file_deleted(result_data, action_params)
        elif action_type in ("delete_directory", "file_delete_directory"):
            return self._verify_directory_deleted(result_data, action_params)
        elif action_type in ("move_file", "file_move"):
            return self._verify_file_moved(result_data, action_params)
        elif action_type in ("copy_file", "file_copy"):
            return self._verify_file_copied(result_data, action_params)
        elif action_type in ("registry_write_value",):
            return self._verify_registry_write(result_data, action_params)
        elif action_type in ("registry_delete_value",):
            return self._verify_registry_delete(result_data, action_params)
        elif action_type.startswith("gui_move_mouse"):
            return self._verify_mouse_position(result_data, action_params)
        elif action_type.startswith("gui_click"):
            return self._verify_mouse_click(result_data, action_params)
        else:
            # For other action types, verification passes by default
            logger.debug(f"No specific verification for action type: {action_type}")
            return VerificationResult(
                verified=True,
                action_type=action_type,
                message=f"No side-effect verification required for {action_type}",
                details={"skipped": True},
            )

    def _verify_file_created(
        self, result_data: Dict[str, Any], action_params: Dict[str, Any]
    ) -> VerificationResult:
        """Verify that a file was created."""
        file_path = result_data.get("file") or action_params.get("file_path")

        if not file_path:
            return VerificationResult(
                verified=False,
                action_type="create_file",
                message="Cannot verify file creation: no file path provided",
                error="Missing file path in result or params",
            )

        path = Path(file_path).expanduser().resolve()

        if path.exists() and path.is_file():
            size = path.stat().st_size
            return VerificationResult(
                verified=True,
                action_type="create_file",
                message=f"Verified file exists: {path}",
                details={"path": str(path), "size_bytes": size, "exists": True},
            )
        else:
            return VerificationResult(
                verified=False,
                action_type="create_file",
                message=f"File does not exist after creation: {path}",
                error=f"Expected file at {path} but it was not found",
                details={"path": str(path), "exists": False},
            )

    def _verify_directory_created(
        self, result_data: Dict[str, Any], action_params: Dict[str, Any]
    ) -> VerificationResult:
        """Verify that a directory was created."""
        dir_path = result_data.get("directory") or action_params.get("directory")

        if not dir_path:
            return VerificationResult(
                verified=False,
                action_type="create_directory",
                message="Cannot verify directory creation: no path provided",
                error="Missing directory path in result or params",
            )

        path = Path(dir_path).expanduser().resolve()

        if path.exists() and path.is_dir():
            return VerificationResult(
                verified=True,
                action_type="create_directory",
                message=f"Verified directory exists: {path}",
                details={"path": str(path), "exists": True, "is_directory": True},
            )
        else:
            return VerificationResult(
                verified=False,
                action_type="create_directory",
                message=f"Directory does not exist after creation: {path}",
                error=f"Expected directory at {path} but it was not found",
                details={"path": str(path), "exists": path.exists()},
            )

    def _verify_file_deleted(
        self, result_data: Dict[str, Any], action_params: Dict[str, Any]
    ) -> VerificationResult:
        """Verify that a file was deleted."""
        file_path = result_data.get("file") or action_params.get("file_path")

        if not file_path:
            return VerificationResult(
                verified=False,
                action_type="delete_file",
                message="Cannot verify file deletion: no file path provided",
                error="Missing file path in result or params",
            )

        path = Path(file_path).expanduser().resolve()

        if not path.exists():
            return VerificationResult(
                verified=True,
                action_type="delete_file",
                message=f"Verified file is absent: {path}",
                details={"path": str(path), "exists": False},
            )
        else:
            return VerificationResult(
                verified=False,
                action_type="delete_file",
                message=f"File still exists after deletion: {path}",
                error=f"Expected file at {path} to be deleted but it still exists",
                details={"path": str(path), "exists": True},
            )

    def _verify_directory_deleted(
        self, result_data: Dict[str, Any], action_params: Dict[str, Any]
    ) -> VerificationResult:
        """Verify that a directory was deleted."""
        dir_path = result_data.get("directory") or action_params.get("directory")

        if not dir_path:
            return VerificationResult(
                verified=False,
                action_type="delete_directory",
                message="Cannot verify directory deletion: no path provided",
                error="Missing directory path in result or params",
            )

        path = Path(dir_path).expanduser().resolve()

        if not path.exists():
            return VerificationResult(
                verified=True,
                action_type="delete_directory",
                message=f"Verified directory is absent: {path}",
                details={"path": str(path), "exists": False},
            )
        else:
            return VerificationResult(
                verified=False,
                action_type="delete_directory",
                message=f"Directory still exists after deletion: {path}",
                error=f"Expected directory at {path} to be deleted but it still exists",
                details={"path": str(path), "exists": True},
            )

    def _verify_file_moved(
        self, result_data: Dict[str, Any], action_params: Dict[str, Any]
    ) -> VerificationResult:
        """Verify that a file was moved."""
        source = result_data.get("source") or action_params.get("source")
        destination = result_data.get("destination") or action_params.get("destination")

        if not source or not destination:
            return VerificationResult(
                verified=False,
                action_type="move_file",
                message="Cannot verify file move: missing source or destination",
                error="Missing source or destination in result or params",
            )

        src_path = Path(source).expanduser().resolve()
        dst_path = Path(destination).expanduser().resolve()

        # Source should not exist, destination should exist
        src_exists = src_path.exists()
        dst_exists = dst_path.exists()

        if not src_exists and dst_exists:
            return VerificationResult(
                verified=True,
                action_type="move_file",
                message=f"Verified file moved from {src_path} to {dst_path}",
                details={
                    "source": str(src_path),
                    "destination": str(dst_path),
                    "source_exists": False,
                    "destination_exists": True,
                },
            )
        else:
            return VerificationResult(
                verified=False,
                action_type="move_file",
                message="File move verification failed",
                error="Expected source absent and destination present",
                details={
                    "source": str(src_path),
                    "destination": str(dst_path),
                    "source_exists": src_exists,
                    "destination_exists": dst_exists,
                },
            )

    def _verify_file_copied(
        self, result_data: Dict[str, Any], action_params: Dict[str, Any]
    ) -> VerificationResult:
        """Verify that a file was copied."""
        source = result_data.get("source") or action_params.get("source")
        destination = result_data.get("destination") or action_params.get("destination")

        if not source or not destination:
            return VerificationResult(
                verified=False,
                action_type="copy_file",
                message="Cannot verify file copy: missing source or destination",
                error="Missing source or destination in result or params",
            )

        src_path = Path(source).expanduser().resolve()
        dst_path = Path(destination).expanduser().resolve()

        # Both source and destination should exist
        src_exists = src_path.exists()
        dst_exists = dst_path.exists()

        if src_exists and dst_exists:
            return VerificationResult(
                verified=True,
                action_type="copy_file",
                message=f"Verified file copied from {src_path} to {dst_path}",
                details={
                    "source": str(src_path),
                    "destination": str(dst_path),
                    "source_exists": True,
                    "destination_exists": True,
                },
            )
        else:
            return VerificationResult(
                verified=False,
                action_type="copy_file",
                message="File copy verification failed",
                error="Expected both source and destination to exist",
                details={
                    "source": str(src_path),
                    "destination": str(dst_path),
                    "source_exists": src_exists,
                    "destination_exists": dst_exists,
                },
            )

    def _verify_registry_write(
        self, result_data: Dict[str, Any], action_params: Dict[str, Any]
    ) -> VerificationResult:
        """Verify that a registry value was written (Windows only)."""
        import platform

        if platform.system() != "Windows":
            return VerificationResult(
                verified=True,
                action_type="registry_write_value",
                message="Registry verification skipped (not on Windows)",
                details={"skipped": True, "reason": "not_windows"},
            )

        root_key = action_params.get("root_key", "")
        subkey_path = action_params.get("subkey_path", "")
        value_name = action_params.get("value_name", "")
        expected_value = action_params.get("value")

        if not all([root_key, subkey_path, value_name]):
            return VerificationResult(
                verified=False,
                action_type="registry_write_value",
                message="Cannot verify registry write: missing key information",
                error="Missing root_key, subkey_path, or value_name",
            )

        try:
            import winreg  # type: ignore[import]

            root_keys = {
                "HKEY_CURRENT_USER": winreg.HKEY_CURRENT_USER,  # type: ignore[attr-defined]
                "HKCU": winreg.HKEY_CURRENT_USER,  # type: ignore[attr-defined]
                "HKEY_LOCAL_MACHINE": winreg.HKEY_LOCAL_MACHINE,  # type: ignore[attr-defined]
                "HKLM": winreg.HKEY_LOCAL_MACHINE,  # type: ignore[attr-defined]
                "HKEY_CLASSES_ROOT": winreg.HKEY_CLASSES_ROOT,  # type: ignore[attr-defined]
                "HKCR": winreg.HKEY_CLASSES_ROOT,  # type: ignore[attr-defined]
            }

            root = root_keys.get(root_key.upper())
            if root is None:
                return VerificationResult(
                    verified=False,
                    action_type="registry_write_value",
                    message=f"Unknown registry root key: {root_key}",
                    error=f"Invalid root key: {root_key}",
                )

            with winreg.OpenKey(root, subkey_path) as key:  # type: ignore[attr-defined]
                actual_value, _ = winreg.QueryValueEx(key, value_name)  # type: ignore[attr-defined]

            if expected_value is not None and actual_value == expected_value:
                return VerificationResult(
                    verified=True,
                    action_type="registry_write_value",
                    message="Verified registry value matches",
                    details={
                        "key": f"{root_key}\\{subkey_path}",
                        "value_name": value_name,
                        "value": actual_value,
                    },
                )
            elif expected_value is None:
                # Just verify the value exists
                return VerificationResult(
                    verified=True,
                    action_type="registry_write_value",
                    message="Verified registry value exists",
                    details={
                        "key": f"{root_key}\\{subkey_path}",
                        "value_name": value_name,
                        "value": actual_value,
                    },
                )
            else:
                return VerificationResult(
                    verified=False,
                    action_type="registry_write_value",
                    message="Registry value does not match expected",
                    error=f"Expected {expected_value}, got {actual_value}",
                    details={
                        "expected": expected_value,
                        "actual": actual_value,
                    },
                )
        except FileNotFoundError:
            return VerificationResult(
                verified=False,
                action_type="registry_write_value",
                message="Registry key or value not found",
                error=f"Key {root_key}\\{subkey_path}\\{value_name} not found",
            )
        except Exception as e:
            return VerificationResult(
                verified=False,
                action_type="registry_write_value",
                message=f"Registry verification error: {str(e)}",
                error=str(e),
            )

    def _verify_registry_delete(
        self, result_data: Dict[str, Any], action_params: Dict[str, Any]
    ) -> VerificationResult:
        """Verify that a registry value was deleted (Windows only)."""
        import platform

        if platform.system() != "Windows":
            return VerificationResult(
                verified=True,
                action_type="registry_delete_value",
                message="Registry verification skipped (not on Windows)",
                details={"skipped": True, "reason": "not_windows"},
            )

        root_key = action_params.get("root_key", "")
        subkey_path = action_params.get("subkey_path", "")
        value_name = action_params.get("value_name", "")

        if not all([root_key, subkey_path, value_name]):
            return VerificationResult(
                verified=False,
                action_type="registry_delete_value",
                message="Cannot verify registry delete: missing key information",
                error="Missing root_key, subkey_path, or value_name",
            )

        try:
            import winreg  # type: ignore[import]

            root_keys = {
                "HKEY_CURRENT_USER": winreg.HKEY_CURRENT_USER,  # type: ignore[attr-defined]
                "HKCU": winreg.HKEY_CURRENT_USER,  # type: ignore[attr-defined]
                "HKEY_LOCAL_MACHINE": winreg.HKEY_LOCAL_MACHINE,  # type: ignore[attr-defined]
                "HKLM": winreg.HKEY_LOCAL_MACHINE,  # type: ignore[attr-defined]
                "HKEY_CLASSES_ROOT": winreg.HKEY_CLASSES_ROOT,  # type: ignore[attr-defined]
                "HKCR": winreg.HKEY_CLASSES_ROOT,  # type: ignore[attr-defined]
            }

            root = root_keys.get(root_key.upper())
            if root is None:
                return VerificationResult(
                    verified=False,
                    action_type="registry_delete_value",
                    message=f"Unknown registry root key: {root_key}",
                    error=f"Invalid root key: {root_key}",
                )

            try:
                with winreg.OpenKey(root, subkey_path) as key:  # type: ignore[attr-defined]
                    winreg.QueryValueEx(key, value_name)  # type: ignore[attr-defined]
                # If we get here, value still exists
                return VerificationResult(
                    verified=False,
                    action_type="registry_delete_value",
                    message="Registry value still exists after deletion",
                    error=f"Value {value_name} still exists",
                )
            except FileNotFoundError:
                # Value doesn't exist - this is what we want
                return VerificationResult(
                    verified=True,
                    action_type="registry_delete_value",
                    message="Verified registry value is absent",
                    details={
                        "key": f"{root_key}\\{subkey_path}",
                        "value_name": value_name,
                        "exists": False,
                    },
                )
        except Exception as e:
            return VerificationResult(
                verified=False,
                action_type="registry_delete_value",
                message=f"Registry verification error: {str(e)}",
                error=str(e),
            )

    def _verify_mouse_position(
        self, result_data: Dict[str, Any], action_params: Dict[str, Any]
    ) -> VerificationResult:
        """Verify mouse was moved to expected position."""
        expected_x = action_params.get("x")
        expected_y = action_params.get("y")

        if expected_x is None or expected_y is None:
            return VerificationResult(
                verified=True,
                action_type="gui_move_mouse",
                message="No position verification (coordinates not provided)",
                details={"skipped": True},
            )

        try:
            import pyautogui

            actual_x, actual_y = pyautogui.position()
            # Allow some tolerance for mouse position (pixels)
            tolerance = 5
            x_match = abs(actual_x - expected_x) <= tolerance
            y_match = abs(actual_y - expected_y) <= tolerance

            if x_match and y_match:
                return VerificationResult(
                    verified=True,
                    action_type="gui_move_mouse",
                    message=f"Verified mouse at ({actual_x}, {actual_y})",
                    details={
                        "expected": {"x": expected_x, "y": expected_y},
                        "actual": {"x": actual_x, "y": actual_y},
                    },
                )
            else:
                return VerificationResult(
                    verified=False,
                    action_type="gui_move_mouse",
                    message="Mouse position mismatch",
                    error=f"Expected ({expected_x}, {expected_y}), got ({actual_x}, {actual_y})",
                    details={
                        "expected": {"x": expected_x, "y": expected_y},
                        "actual": {"x": actual_x, "y": actual_y},
                    },
                )
        except ImportError:
            return VerificationResult(
                verified=True,
                action_type="gui_move_mouse",
                message="pyautogui not available for verification",
                details={"skipped": True, "reason": "pyautogui_unavailable"},
            )
        except Exception as e:
            return VerificationResult(
                verified=False,
                action_type="gui_move_mouse",
                message=f"Mouse position verification error: {str(e)}",
                error=str(e),
            )

    def _verify_mouse_click(
        self, result_data: Dict[str, Any], action_params: Dict[str, Any]
    ) -> VerificationResult:
        """
        Verify mouse click occurred.

        Note: Actual click verification is challenging. We can only verify
        the mouse is in the expected position after the click.
        """
        expected_x = action_params.get("x")
        expected_y = action_params.get("y")

        if expected_x is None or expected_y is None:
            return VerificationResult(
                verified=True,
                action_type="gui_click_mouse",
                message="Click executed (position verification skipped)",
                details={"skipped": True, "reason": "no_coordinates"},
            )

        try:
            import pyautogui

            actual_x, actual_y = pyautogui.position()
            tolerance = 5
            x_match = abs(actual_x - expected_x) <= tolerance
            y_match = abs(actual_y - expected_y) <= tolerance

            if x_match and y_match:
                return VerificationResult(
                    verified=True,
                    action_type="gui_click_mouse",
                    message=f"Click verified at ({actual_x}, {actual_y})",
                    details={
                        "expected": {"x": expected_x, "y": expected_y},
                        "actual": {"x": actual_x, "y": actual_y},
                    },
                )
            else:
                return VerificationResult(
                    verified=False,
                    action_type="gui_click_mouse",
                    message="Click position mismatch",
                    error=f"Expected ({expected_x}, {expected_y}), got ({actual_x}, {actual_y})",
                    details={
                        "expected": {"x": expected_x, "y": expected_y},
                        "actual": {"x": actual_x, "y": actual_y},
                    },
                )
        except ImportError:
            return VerificationResult(
                verified=True,
                action_type="gui_click_mouse",
                message="pyautogui not available for verification",
                details={"skipped": True, "reason": "pyautogui_unavailable"},
            )
        except Exception as e:
            return VerificationResult(
                verified=False,
                action_type="gui_click_mouse",
                message=f"Click verification error: {str(e)}",
                error=str(e),
            )
