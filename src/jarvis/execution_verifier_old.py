"""
Execution verifier module for Jarvis.

Provides post-execution verification logic that checks if actions actually
completed successfully, along with detailed diagnostic reporting for failures.
"""

import logging
import os
import platform
import subprocess
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from jarvis.action_executor import ActionResult

# Try to import psutil, make it optional
try:
    import psutil
    PSUTIL_AVAILABLE = True
except ImportError:
    PSUTIL_AVAILABLE = False
    psutil = None

logger = logging.getLogger(__name__)

if not PSUTIL_AVAILABLE:
    logger.warning("psutil not installed, process diagnostics will be limited")


class VerificationResult:
    """Result of an action verification attempt."""

    def __init__(
        self,
        verified: bool,
        verification_method: str,
        details: Dict[str, Any],
        error_message: Optional[str] = None,
    ):
        """
        Initialize verification result.

        Args:
            verified: Whether the action was verified as successful
            verification_method: Method used for verification
            details: Additional verification details
            error_message: Error message if verification failed
        """
        self.verified = verified
        self.verification_method = verification_method
        self.details = details
        self.error_message = error_message

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "verified": self.verified,
            "verification_method": self.verification_method,
            "details": self.details,
            "error_message": self.error_message,
        }


class DiagnosticsCollector:
    """Collects diagnostic information about action failures."""

    @staticmethod
    def collect_disk_space_diagnostics(path: str) -> Dict[str, Any]:
        """Collect disk space information for a path."""
        try:
            stat = os.statvfs(path) if hasattr(os, "statvfs") else None
            if stat:
                return {
                    "total_bytes": stat.f_frsize * stat.f_blocks,
                    "free_bytes": stat.f_frsize * stat.f_bavail,
                    "used_bytes": stat.f_frsize * (stat.f_blocks - stat.f_bfree),
                    "free_percent": (stat.f_bavail / stat.f_blocks) * 100,
                }
            # Windows fallback
            import ctypes

            free_bytes = ctypes.c_ulonglong(0)
            total_bytes = ctypes.c_ulonglong(0)
            ctypes.windll.kernel32.GetDiskFreeSpaceExW(
                ctypes.c_wchar_p(path),
                ctypes.byref(free_bytes),
                ctypes.byref(total_bytes),
                None,
            )
            return {
                "total_bytes": total_bytes.value,
                "free_bytes": free_bytes.value,
                "used_bytes": total_bytes.value - free_bytes.value,
                "free_percent": (free_bytes.value / total_bytes.value) * 100,
            }
        except Exception as e:
            logger.warning(f"Could not collect disk space diagnostics: {e}")
            return {"error": str(e)}

    @staticmethod
    def collect_permission_diagnostics(path: str) -> Dict[str, Any]:
        """Collect permission information for a path."""
        try:
            path_obj = Path(path).expanduser().resolve()
            exists = path_obj.exists()
            is_readable = os.access(path_obj, os.R_OK) if exists else None
            is_writable = os.access(path_obj, os.W_OK) if exists else None
            is_executable = os.access(path_obj, os.X_OK) if exists else None

            # Get file stats if exists
            stats = {}
            if exists:
                stat_info = path_obj.stat()
                stats = {
                    "mode": oct(stat_info.st_mode),
                    "uid": stat_info.st_uid,
                    "gid": stat_info.st_gid,
                    "size": stat_info.st_size,
                    "modified": stat_info.st_mtime,
                }

            return {
                "path": str(path_obj),
                "exists": exists,
                "is_readable": is_readable,
                "is_writable": is_writable,
                "is_executable": is_executable,
                "stats": stats,
            }
        except Exception as e:
            logger.warning(f"Could not collect permission diagnostics: {e}")
            return {"error": str(e)}

    @staticmethod
    def collect_process_diagnostics(pid: Optional[int] = None) -> Dict[str, Any]:
        """Collect process information."""
        if not PSUTIL_AVAILABLE:
            return {"error": "psutil not installed, process diagnostics unavailable"}

        try:
            if pid:
                try:
                    process = psutil.Process(pid)
                    return {
                        "pid": pid,
                        "name": process.name(),
                        "status": process.status(),
                        "create_time": process.create_time(),
                        "cmdline": process.cmdline(),
                        "exe": process.exe(),
                        "running": process.is_running(),
                    }
                except psutil.NoSuchProcess:
                    return {"pid": pid, "running": False, "error": "Process not found"}

            # List recent processes
            recent_processes = []
            for proc in psutil.process_iter(["pid", "name", "create_time", "status"]):
                try:
                    proc_info = proc.info
                    # Filter to processes created in last 30 seconds
                    if (
                        proc_info["create_time"]
                        and (time.time() - proc_info["create_time"]) < 30
                    ):
                        recent_processes.append(proc_info)
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    pass

            return {
                "recent_processes": recent_processes[:20],  # Limit to 20 most recent
                "count": len(recent_processes),
            }
        except Exception as e:
            logger.warning(f"Could not collect process diagnostics: {e}")
            return {"error": str(e)}
    @staticmethod
    def collect_network_diagnostics() -> Dict[str, Any]:
        """Collect network information."""
        try:
            import socket

            hostname = socket.gethostname()
            # Check internet connectivity
            try:
                socket.create_connection(("8.8.8.8", 53), timeout=2)
                internet_connected = True
            except OSError:
                internet_connected = False

            return {
                "hostname": hostname,
                "platform": platform.system(),
                "internet_connected": internet_connected,
            }
        except Exception as e:
            logger.warning(f"Could not collect network diagnostics: {e}")
            return {"error": str(e)}

    @staticmethod
    def collect_file_lock_diagnostics(path: str) -> Dict[str, Any]:
        """Check if a file is locked by another process."""
        try:
            path_obj = Path(path).expanduser().resolve()

            if not path_obj.exists():
                return {"locked": False, "reason": "File does not exist"}

            # Try to open the file exclusively
            try:
                with open(path_obj, "r+b") as f:
                    pass
                return {"locked": False, "reason": "File is accessible"}
            except IOError as e:
                if "being used by another process" in str(e).lower():
                    # Try to identify which process has the file open
                    if sys.platform == "win32":
                        try:
                            import ctypes

                            handle = ctypes.windll.kernel32.CreateFileW(
                                path,
                                0x80000000,  # GENERIC_READ
                                0,  # No sharing
                                None,
                                3,  # OPEN_EXISTING
                                0,
                                None,
                            )
                            if handle == -1:
                                error_code = ctypes.get_last_error()
                                return {
                                    "locked": True,
                                    "reason": f"File locked (error: {error_code})",
                                }
                            ctypes.windll.kernel32.CloseHandle(handle)
                        except Exception:
                            pass

                    return {
                        "locked": True,
                        "reason": f"File is locked: {str(e)}",
                    }
                raise

        except Exception as e:
            logger.warning(f"Could not collect file lock diagnostics: {e}")
            return {"error": str(e)}


class ApplicationVerifier:
    """Verifies application launches."""

    def __init__(self, timeout: int = 5):
        """
        Initialize application verifier.

        Args:
            timeout: Timeout in seconds for verification checks
        """
        self.timeout = timeout

    def verify_application_launch(
        self, application_path: str, expected_window: Optional[str] = None
    ) -> VerificationResult:
        """
        Verify that an application launched successfully.

        Args:
            application_path: Path to the application executable
            expected_window: Optional expected window title

        Returns:
            VerificationResult with verification status
        """
        logger.info(f"Verifying application launch: {application_path}")
        app_name = Path(application_path).stem.lower()

        # Method 1: Check for process existence
        process_result = self._check_process_exists(app_name)
        if process_result.verified:
            logger.info(f"Application verified via process check: {application_path}")
            return process_result

        # Method 2: Check for window (Windows only)
        if sys.platform == "win32":
            window_result = self._check_window_exists(expected_window or app_name)
            if window_result.verified:
                logger.info(f"Application verified via window check: {application_path}")
                return window_result

        # Method 3: Try to ping the application
        ping_result = self._ping_application(application_path)
        if ping_result.verified:
            logger.info(f"Application verified via ping: {application_path}")
            return ping_result

        # Collect diagnostics
        diagnostics = self._collect_launch_diagnostics(application_path)

        return VerificationResult(
            verified=False,
            verification_method="none",
            details=diagnostics,
            error_message="Application could not be verified as running",
        )

    def _check_process_exists(self, app_name: str) -> VerificationResult:
        """Check if the application process is running."""
        try:
            for proc in psutil.process_iter(["name", "exe", "cmdline"]):
                try:
                    proc_info = proc.info
                    if proc_info["exe"]:
                        exe_lower = proc_info["exe"].lower()
                        if app_name in exe_lower or exe_lower.endswith(f"{app_name}.exe"):
                            return VerificationResult(
                                verified=True,
                                verification_method="process_check",
                                details={
                                    "pid": proc.pid,
                                    "name": proc_info["name"],
                                    "exe": proc_info["exe"],
                                },
                            )
                    if proc_info["cmdline"]:
                        cmdline_str = " ".join(proc_info["cmdline"]).lower()
                        if app_name in cmdline_str:
                            return VerificationResult(
                                verified=True,
                                verification_method="process_check",
                                details={
                                    "pid": proc.pid,
                                    "name": proc_info["name"],
                                    "cmdline": proc_info["cmdline"],
                                },
                            )
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    continue

            return VerificationResult(
                verified=False,
                verification_method="process_check",
                details={"reason": "Process not found"},
            )
        except Exception as e:
            logger.warning(f"Error checking process existence: {e}")
            return VerificationResult(
                verified=False,
                verification_method="process_check",
                details={"error": str(e)},
            )

    def _check_window_exists(self, window_title: str) -> VerificationResult:
        """Check if a window with the expected title exists (Windows only)."""
        try:
            import ctypes
            import ctypes.wintypes

            # Define Windows API functions
            EnumWindows = ctypes.windll.user32.EnumWindows
            EnumWindowsProc = ctypes.WINFUNCTYPE(
                ctypes.c_bool, ctypes.POINTER(ctypes.c_int), ctypes.POINTER(ctypes.c_int)
            )
            GetWindowText = ctypes.windll.user32.GetWindowTextW
            GetWindowTextLength = ctypes.windll.user32.GetWindowTextLengthW

            windows = []

            def callback(hwnd, lparam):
                length = GetWindowTextLength(hwnd)
                if length > 0:
                    buffer = ctypes.create_unicode_buffer(length + 1)
                    GetWindowText(hwnd, buffer, length + 1)
                    if window_title.lower() in buffer.value.lower():
                        windows.append(hwnd)
                return True

            EnumWindows(EnumWindowsProc(callback), 0)

            if windows:
                return VerificationResult(
                    verified=True,
                    verification_method="window_check",
                    details={"window_count": len(windows), "window_title": window_title},
                )

            return VerificationResult(
                verified=False,
                verification_method="window_check",
                details={"reason": "No matching window found"},
            )
        except Exception as e:
            logger.warning(f"Error checking window existence: {e}")
            return VerificationResult(
                verified=False,
                verification_method="window_check",
                details={"error": str(e)},
            )

    def _ping_application(self, application_path: str) -> VerificationResult:
        """Try to ping the application (for servers/networked apps)."""
        # For local desktop apps, this is less applicable
        # Just return not verified
        return VerificationResult(
            verified=False,
            verification_method="ping_check",
            details={"reason": "Ping check not applicable for desktop apps"},
        )

    def _collect_launch_diagnostics(self, application_path: str) -> Dict[str, Any]:
        """Collect diagnostics about why application launch may have failed."""
        diagnostics = {}

        # Check if application exists
        path_obj = Path(application_path).expanduser().resolve()
        diagnostics["application_exists"] = path_obj.exists()

        if not diagnostics["application_exists"]:
            # Check if it might be in PATH
            path_dirs = os.environ.get("PATH", "").split(os.pathsep)
            found_in_path = False
            for path_dir in path_dirs:
                test_path = Path(path_dir) / Path(application_path).name
                if test_path.exists():
                    diagnostics["found_in_path"] = str(test_path)
                    found_in_path = True
                    break
            if not found_in_path:
                diagnostics["found_in_path"] = None

        # Check file permissions
        if diagnostics["application_exists"]:
            diagnostics["executable"] = os.access(path_obj, os.X_OK)
            diagnostics["readable"] = os.access(path_obj, os.R_OK)

        # Check recent process launches
        process_diagnostics = DiagnosticsCollector.collect_process_diagnostics()
        diagnostics["recent_processes"] = process_diagnostics.get("recent_processes", [])

        return diagnostics


class FileVerifier:
    """Verifies file operations."""

    def verify_file_creation(
        self, file_path: str, expected_content: Optional[str] = None
    ) -> VerificationResult:
        """
        Verify that a file was created successfully.

        Args:
            file_path: Path to the file
            expected_content: Optional expected content

        Returns:
            VerificationResult with verification status
        """
        logger.info(f"Verifying file creation: {file_path}")
        path_obj = Path(file_path).expanduser().resolve()

        # Check 1: File exists
        if not path_obj.exists():
            return VerificationResult(
                verified=False,
                verification_method="existence_check",
                details=DiagnosticsCollector.collect_permission_diagnostics(str(path_obj)),
                error_message="File does not exist",
            )

        # Check 2: File is not empty
        file_size = path_obj.stat().st_size
        if file_size == 0:
            return VerificationResult(
                verified=False,
                verification_method="size_check",
                details={"size_bytes": 0},
                error_message="File is empty",
            )

        # Check 3: Content verification (if expected content provided)
        if expected_content is not None:
            try:
                actual_content = path_obj.read_text()
                if expected_content not in actual_content and actual_content not in expected_content:
                    return VerificationResult(
                        verified=False,
                        verification_method="content_check",
                        details={
                            "expected_length": len(expected_content),
                            "actual_length": len(actual_content),
                        },
                        error_message="File content does not match expected content",
                    )
            except Exception as e:
                logger.warning(f"Could not verify file content: {e}")

        return VerificationResult(
            verified=True,
            verification_method="existence_check",
            details={
                "size_bytes": file_size,
                "path": str(path_obj),
                "readable": os.access(path_obj, os.R_OK),
                "writable": os.access(path_obj, os.W_OK),
            },
        )

    def verify_file_deletion(self, file_path: str) -> VerificationResult:
        """
        Verify that a file was deleted successfully.

        Args:
            file_path: Path to the file

        Returns:
            VerificationResult with verification status
        """
        logger.info(f"Verifying file deletion: {file_path}")
        path_obj = Path(file_path).expanduser().resolve()

        if path_obj.exists():
            return VerificationResult(
                verified=False,
                verification_method="existence_check",
                details={"path": str(path_obj)},
                error_message="File still exists",
            )

        return VerificationResult(
            verified=True,
            verification_method="existence_check",
            details={"path": str(path_obj)},
        )

    def verify_file_move(
        self, source: str, destination: str
    ) -> VerificationResult:
        """
        Verify that a file was moved successfully.

        Args:
            source: Original file path
            destination: Destination file path

        Returns:
            VerificationResult with verification status
        """
        logger.info(f"Verifying file move: {source} -> {destination}")
        source_obj = Path(source).expanduser().resolve()
        dest_obj = Path(destination).expanduser().resolve()

        # Check source no longer exists
        if source_obj.exists():
            return VerificationResult(
                verified=False,
                verification_method="existence_check",
                details={"source_exists": True, "destination_exists": dest_obj.exists()},
                error_message="Source file still exists",
            )

        # Check destination exists
        if not dest_obj.exists():
            return VerificationResult(
                verified=False,
                verification_method="existence_check",
                details={"source_exists": False, "destination_exists": False},
                error_message="Destination file does not exist",
            )

        return VerificationResult(
            verified=True,
            verification_method="existence_check",
            details={
                "destination_path": str(dest_obj),
                "size_bytes": dest_obj.stat().st_size,
            },
        )


class InputVerifier:
    """Verifies text input operations."""

    def __init__(self, timeout: int = 2):
        """
        Initialize input verifier.

        Args:
            timeout: Timeout in seconds for verification
        """
        self.timeout = timeout

    def verify_text_input(
        self, text: str, method: str = "keyboard"
    ) -> VerificationResult:
        """
        Verify that text was input successfully.

        Args:
            text: Text that was supposed to be input
            method: Method used (keyboard, clipboard, etc.)

        Returns:
            VerificationResult with verification status
        """
        logger.info(f"Verifying text input (method={method}): {text[:50]}...")

        # Method 1: Check clipboard (if clipboard method was used)
        if method == "clipboard":
            clipboard_result = self._verify_clipboard_content(text)
            if clipboard_result.verified:
                return clipboard_result

        # Method 2: Try to verify via OCR (if GUI is available)
        ocr_result = self._verify_via_ocr(text)
        if ocr_result.verified:
            return ocr_result

        # For keyboard input, we can't easily verify without OCR
        # Return partial verification
        return VerificationResult(
            verified=False,
            verification_method="limited",
            details={"method": method, "text_length": len(text)},
            error_message="Cannot fully verify keyboard input without OCR",
        )

    def _verify_clipboard_content(self, expected_text: str) -> VerificationResult:
        """Verify clipboard contains expected text."""
        try:
            import pyperclip

            clipboard_content = pyperclip.paste()
            if expected_text in clipboard_content or clipboard_content in expected_text:
                return VerificationResult(
                    verified=True,
                    verification_method="clipboard_check",
                    details={"text_length": len(clipboard_content)},
                )
            return VerificationResult(
                verified=False,
                verification_method="clipboard_check",
                details={
                    "expected_length": len(expected_text),
                    "actual_length": len(clipboard_content),
                },
                error_message="Clipboard content does not match",
            )
        except ImportError:
            logger.warning("pyperclip not available for clipboard verification")
            return VerificationResult(
                verified=False,
                verification_method="clipboard_check",
                details={"error": "pyperclip not installed"},
                error_message="Clipboard verification not available",
            )
        except Exception as e:
            logger.warning(f"Error verifying clipboard content: {e}")
            return VerificationResult(
                verified=False,
                verification_method="clipboard_check",
                details={"error": str(e)},
                error_message=f"Clipboard verification failed: {str(e)}",
            )

    def _verify_via_ocr(self, expected_text: str) -> VerificationResult:
        """Verify text via OCR of active window or screen."""
        try:
            # This would require OCR integration
            # For now, just note that OCR verification is available but not implemented
            return VerificationResult(
                verified=False,
                verification_method="ocr_check",
                details={"expected_text": expected_text},
                error_message="OCR verification not yet implemented",
            )
        except Exception as e:
            return VerificationResult(
                verified=False,
                verification_method="ocr_check",
                details={"error": str(e)},
                error_message=f"OCR verification failed: {str(e)}",
            )


class DirectoryVerifier:
    """Verifies directory operations."""

    def verify_directory_creation(self, directory: str) -> VerificationResult:
        """
        Verify that a directory was created successfully.

        Args:
            directory: Directory path

        Returns:
            VerificationResult with verification status
        """
        logger.info(f"Verifying directory creation: {directory}")
        path_obj = Path(directory).expanduser().resolve()

        # Check 1: Directory exists
        if not path_obj.exists():
            return VerificationResult(
                verified=False,
                verification_method="existence_check",
                details=DiagnosticsCollector.collect_permission_diagnostics(str(path_obj)),
                error_message="Directory does not exist",
            )

        # Check 2: It's actually a directory
        if not path_obj.is_dir():
            return VerificationResult(
                verified=False,
                verification_method="type_check",
                details={"path": str(path_obj), "is_dir": False},
                error_message="Path exists but is not a directory",
            )

        # Check 3: Directory is accessible
        readable = os.access(path_obj, os.R_OK)
        writable = os.access(path_obj, os.W_OK)

        return VerificationResult(
            verified=True,
            verification_method="existence_check",
            details={
                "path": str(path_obj),
                "readable": readable,
                "writable": writable,
                "empty": len(list(path_obj.iterdir())) == 0,
            },
        )


class ExecutionVerifier:
    """Main execution verifier that coordinates all verification types."""

    def __init__(self, timeout: int = 5):
        """
        Initialize execution verifier.

        Args:
            timeout: Default timeout for verification operations
        """
        self.timeout = timeout
        self.app_verifier = ApplicationVerifier(timeout=timeout)
        self.file_verifier = FileVerifier()
        self.input_verifier = InputVerifier(timeout=timeout)
        self.dir_verifier = DirectoryVerifier()

    def verify_action(
        self,
        action_type: str,
        action_result: ActionResult,
        **verification_params: Any,
    ) -> VerificationResult:
        """
        Verify an action based on its type.

        Args:
            action_type: Type of action performed
            action_result: Result from the action execution
            **verification_params: Additional parameters for verification

        Returns:
            VerificationResult with verification status
        """
        logger.info(f"Verifying action type: {action_type}")

        # If action failed, verification also fails
        if not action_result.success:
            return VerificationResult(
                verified=False,
                verification_method="precheck",
                details={"action_error": action_result.error},
                error_message=f"Action execution failed: {action_result.error}",
            )

        # Route to appropriate verifier
        if action_type.startswith("subprocess_open_application"):
            app_path = verification_params.get("application_path", "")
            return self.app_verifier.verify_application_launch(app_path)

        elif action_type.startswith("file_create"):
            file_path = verification_params.get("file_path", "")
            content = verification_params.get("content", "")
            return self.file_verifier.verify_file_creation(file_path, content or None)

        elif action_type.startswith("file_delete"):
            file_path = verification_params.get("file_path", "")
            return self.file_verifier.verify_file_deletion(file_path)

        elif action_type.startswith("file_move"):
            source = verification_params.get("source", "")
            destination = verification_params.get("destination", "")
            return self.file_verifier.verify_file_move(source, destination)

        elif action_type.startswith("typing_type_text"):
            text = verification_params.get("text", "")
            return self.input_verifier.verify_text_input(text, method="keyboard")

        elif action_type.startswith("file_delete_directory"):
            directory = verification_params.get("directory", "")
            # For deletion, we invert the verification
            path_obj = Path(directory).expanduser().resolve()
            if path_obj.exists():
                return VerificationResult(
                    verified=False,
                    verification_method="existence_check",
                    details={"path": str(path_obj)},
                    error_message="Directory still exists",
                )
            return VerificationResult(
                verified=True,
                verification_method="existence_check",
                details={"path": str(path_obj)},
            )

        # For actions we can't verify, assume success
        return VerificationResult(
            verified=True,
            verification_method="not_applicable",
            details={"reason": f"Verification not applicable for {action_type}"},
        )
