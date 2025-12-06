"""
System actions module.

Provides a unified interface for system-level actions through specialized
action modules while enforcing safety checks and dry-run semantics.
"""

import logging
from typing import Any, Dict, Optional

from jarvis.action_executor import ActionExecutor, ActionResult

from .files import FileActions
from .gui_control import GUIControlActions
from .typing import TypingActions
from .registry import RegistryActions
from .ocr import OCRActions
from .powershell import PowerShellActions
from .subprocess_actions import SubprocessActions

logger = logging.getLogger(__name__)


class SystemActionRouter:
    """
    Router for system action modules.

    Provides a unified interface to access all system action capabilities
    while maintaining safety checks and dry-run semantics.
    """

    def __init__(
        self,
        action_executor: Optional[ActionExecutor] = None,
        dry_run: bool = False,
        tesseract_path: Optional[str] = None,
        action_timeout: int = 30
    ) -> None:
        """
        Initialize the system action router.

        Args:
            action_executor: ActionExecutor instance for file operations
            dry_run: If True, preview actions without executing
            tesseract_path: Optional path to tesseract executable
            action_timeout: Timeout for action operations in seconds
        """
        self.dry_run = dry_run
        self.action_timeout = action_timeout
        
        # Initialize action modules
        self.files = FileActions(action_executor) if action_executor else None
        self.gui_control = GUIControlActions(dry_run=dry_run)
        self.typing = TypingActions(dry_run=dry_run)
        self.registry = RegistryActions(dry_run=dry_run)
        self.ocr = OCRActions(dry_run=dry_run, tesseract_path=tesseract_path)
        self.powershell = PowerShellActions(dry_run=dry_run, timeout=action_timeout)
        self.subprocess = SubprocessActions(dry_run=dry_run, timeout=action_timeout)
        
        logger.info("SystemActionRouter initialized")

    def route_action(self, action_type: str, **kwargs: Any) -> ActionResult:
        """
        Route an action to the appropriate module.

        Args:
            action_type: Type of action to perform
            **kwargs: Action-specific parameters

        Returns:
            ActionResult from the executed action

        Raises:
            ValueError: If action_type is not recognized
            RuntimeError: If required module is not available
        """
        logger.info(f"Routing action: {action_type}")
        
        # File operations
        if action_type.startswith("file_"):
            if not self.files:
                return ActionResult(
                    success=False,
                    action_type=action_type,
                    message="File actions not available",
                    error="ActionExecutor not configured",
                    execution_time_ms=0.0
                )
            
            if action_type == "file_list":
                return self.files.list_files(
                    directory=kwargs.get("directory"),
                    recursive=kwargs.get("recursive", False)
                )
            elif action_type == "file_create":
                return self.files.create_file(
                    file_path=kwargs.get("file_path"),
                    content=kwargs.get("content", "")
                )
            elif action_type == "file_delete":
                return self.files.delete_file(
                    file_path=kwargs.get("file_path")
                )
            elif action_type == "file_delete_directory":
                return self.files.delete_directory(
                    directory=kwargs.get("directory")
                )
            elif action_type == "file_move":
                return self.files.move_file(
                    source=kwargs.get("source"),
                    destination=kwargs.get("destination")
                )
            elif action_type == "file_copy":
                return self.files.copy_file(
                    source=kwargs.get("source"),
                    destination=kwargs.get("destination")
                )
            elif action_type == "file_get_info":
                return self.files.get_file_info(
                    file_path=kwargs.get("file_path")
                )
            else:
                raise ValueError(f"Unknown file action: {action_type}")

        # GUI control operations
        elif action_type.startswith("gui_"):
            if action_type == "gui_get_screen_size":
                result = self.gui_control.get_screen_size()
            elif action_type == "gui_capture_screen":
                result = self.gui_control.capture_screen(
                    region=kwargs.get("region")
                )
            elif action_type == "gui_move_mouse":
                result = self.gui_control.move_mouse(
                    x=kwargs.get("x"),
                    y=kwargs.get("y"),
                    duration=kwargs.get("duration", 0.5)
                )
            elif action_type == "gui_click_mouse":
                result = self.gui_control.click_mouse(
                    x=kwargs.get("x"),
                    y=kwargs.get("y"),
                    button=kwargs.get("button", "left"),
                    clicks=kwargs.get("clicks", 1)
                )
            elif action_type == "gui_get_mouse_position":
                result = self.gui_control.get_mouse_position()
            else:
                raise ValueError(f"Unknown GUI action: {action_type}")
            
            # Ensure execution_time_ms is set
            if not hasattr(result, 'execution_time_ms') or result.execution_time_ms is None:
                result.execution_time_ms = 0.0
            return result

        # Typing operations
        elif action_type.startswith("typing_"):
            if action_type == "typing_type_text":
                return self.typing.type_text(
                    text=kwargs.get("text"),
                    interval=kwargs.get("interval", 0.01)
                )
            elif action_type == "typing_press_key":
                return self.typing.press_key(
                    key=kwargs.get("key"),
                    presses=kwargs.get("presses", 1)
                )
            elif action_type == "typing_hotkey":
                return self.typing.hotkey(*kwargs.get("keys", []))
            elif action_type == "typing_copy_to_clipboard":
                return self.typing.copy_to_clipboard(
                    text=kwargs.get("text")
                )
            elif action_type == "typing_paste_from_clipboard":
                return self.typing.paste_from_clipboard()
            elif action_type == "typing_get_clipboard_content":
                return self.typing.get_clipboard_content()
            else:
                raise ValueError(f"Unknown typing action: {action_type}")

        # Registry operations
        elif action_type.startswith("registry_"):
            if action_type == "registry_list_subkeys":
                return self.registry.list_subkeys(
                    root_key=kwargs.get("root_key"),
                    subkey_path=kwargs.get("subkey_path", "")
                )
            elif action_type == "registry_list_values":
                return self.registry.list_values(
                    root_key=kwargs.get("root_key"),
                    subkey_path=kwargs.get("subkey_path", "")
                )
            elif action_type == "registry_read_value":
                return self.registry.read_value(
                    root_key=kwargs.get("root_key"),
                    subkey_path=kwargs.get("subkey_path"),
                    value_name=kwargs.get("value_name")
                )
            elif action_type == "registry_write_value":
                return self.registry.write_value(
                    root_key=kwargs.get("root_key"),
                    subkey_path=kwargs.get("subkey_path"),
                    value_name=kwargs.get("value_name"),
                    value=kwargs.get("value"),
                    value_type=kwargs.get("value_type", "REG_SZ")
                )
            elif action_type == "registry_delete_value":
                return self.registry.delete_value(
                    root_key=kwargs.get("root_key"),
                    subkey_path=kwargs.get("subkey_path"),
                    value_name=kwargs.get("value_name")
                )
            else:
                raise ValueError(f"Unknown registry action: {action_type}")

        # OCR operations
        elif action_type.startswith("ocr_"):
            if action_type == "ocr_extract_from_image":
                return self.ocr.extract_text_from_image(
                    image_path=kwargs.get("image_path"),
                    language=kwargs.get("language", "eng")
                )
            elif action_type == "ocr_extract_from_screen":
                return self.ocr.extract_text_from_screen(
                    region=kwargs.get("region"),
                    language=kwargs.get("language", "eng")
                )
            elif action_type == "ocr_extract_with_boxes":
                return self.ocr.extract_text_with_boxes(
                    image_path=kwargs.get("image_path"),
                    language=kwargs.get("language", "eng")
                )
            elif action_type == "ocr_get_available_languages":
                return self.ocr.get_available_languages()
            elif action_type == "ocr_windows_from_screen":
                return self.ocr.windows_ocr_from_screen(
                    region=kwargs.get("region")
                )
            else:
                raise ValueError(f"Unknown OCR action: {action_type}")

        # PowerShell operations
        elif action_type.startswith("powershell_"):
            if action_type == "powershell_execute":
                result = self.powershell.execute_command(
                    command=kwargs.get("command"),
                    capture_output=kwargs.get("capture_output", True),
                    shell=kwargs.get("shell", False)
                )
            elif action_type == "powershell_execute_script":
                result = self.powershell.execute_script(
                    script_content=kwargs.get("script_content")
                )
            elif action_type == "powershell_get_system_info":
                result = self.powershell.get_system_info()
            elif action_type == "powershell_get_processes":
                result = self.powershell.get_running_processes()
            elif action_type == "powershell_get_services":
                result = self.powershell.get_services(
                    status=kwargs.get("status", "running")
                )
            elif action_type == "powershell_get_programs":
                result = self.powershell.get_installed_programs()
            elif action_type == "powershell_check_file_hash":
                result = self.powershell.check_file_hash(
                    file_path=kwargs.get("file_path"),
                    algorithm=kwargs.get("algorithm", "SHA256")
                )
            else:
                raise ValueError(f"Unknown PowerShell action: {action_type}")
            
            # Ensure execution_time_ms is set
            if not hasattr(result, 'execution_time_ms') or result.execution_time_ms is None:
                result.execution_time_ms = 0.0
            return result

        # Subprocess operations
        elif action_type.startswith("subprocess_"):
            if action_type == "subprocess_execute":
                result = self.subprocess.execute_command(
                    command=kwargs.get("command"),
                    shell=kwargs.get("shell", True),
                    capture_output=kwargs.get("capture_output", True),
                    working_directory=kwargs.get("working_directory"),
                    env=kwargs.get("env")
                )
            elif action_type == "subprocess_open_application":
                result = self.subprocess.open_application(
                    application_path=kwargs.get("application_path"),
                    arguments=kwargs.get("arguments")
                )
            elif action_type == "subprocess_ping":
                result = self.subprocess.ping_host(
                    host=kwargs.get("host"),
                    count=kwargs.get("count", 4)
                )
            elif action_type == "subprocess_get_network":
                result = self.subprocess.get_network_interfaces()
            elif action_type == "subprocess_get_disk_usage":
                result = self.subprocess.get_disk_usage(
                    path=kwargs.get("path", ".")
                )
            elif action_type == "subprocess_get_environment":
                result = self.subprocess.get_environment_variables()
            elif action_type == "subprocess_kill_process":
                result = self.subprocess.kill_process(
                    process_id=kwargs.get("process_id"),
                    force=kwargs.get("force", False)
                )
            elif action_type == "subprocess_list_processes":
                result = self.subprocess.list_processes()
            else:
                raise ValueError(f"Unknown subprocess action: {action_type}")
            
            # Ensure execution_time_ms is set
            if not hasattr(result, 'execution_time_ms') or result.execution_time_ms is None:
                result.execution_time_ms = 0.0
            return result

        else:
            raise ValueError(f"Unknown action type: {action_type}")

    def list_available_actions(self) -> Dict[str, Dict[str, Any]]:
        """
        List all available actions by category.

        Returns:
            Dictionary mapping categories to available actions
        """
        actions = {
            "file": {
                "file_list": "List files in directory",
                "file_create": "Create a file",
                "file_delete": "Delete a file",
                "file_delete_directory": "Delete a directory",
                "file_move": "Move/rename a file",
                "file_copy": "Copy a file",
                "file_get_info": "Get file information"
            },
            "gui": {
                "gui_get_screen_size": "Get screen dimensions",
                "gui_capture_screen": "Capture screenshot",
                "gui_move_mouse": "Move mouse cursor",
                "gui_click_mouse": "Click mouse button",
                "gui_get_mouse_position": "Get mouse position"
            },
            "typing": {
                "typing_type_text": "Type text",
                "typing_press_key": "Press keyboard key",
                "typing_hotkey": "Press key combination",
                "typing_copy_to_clipboard": "Copy text to clipboard",
                "typing_paste_from_clipboard": "Paste from clipboard",
                "typing_get_clipboard_content": "Get clipboard content"
            },
            "registry": {
                "registry_list_subkeys": "List registry subkeys",
                "registry_list_values": "List registry values",
                "registry_read_value": "Read registry value",
                "registry_write_value": "Write registry value",
                "registry_delete_value": "Delete registry value"
            },
            "ocr": {
                "ocr_extract_from_image": "Extract text from image",
                "ocr_extract_from_screen": "Extract text from screen",
                "ocr_extract_with_boxes": "Extract text with bounding boxes",
                "ocr_get_available_languages": "Get available OCR languages",
                "ocr_windows_from_screen": "Windows OCR from screen"
            },
            "powershell": {
                "powershell_execute": "Execute PowerShell command",
                "powershell_execute_script": "Execute PowerShell script",
                "powershell_get_system_info": "Get system information",
                "powershell_get_processes": "Get running processes",
                "powershell_get_services": "Get services",
                "powershell_get_programs": "Get installed programs",
                "powershell_check_file_hash": "Calculate file hash"
            },
            "subprocess": {
                "subprocess_execute": "Execute system command",
                "subprocess_open_application": "Open application",
                "subprocess_ping": "Ping host",
                "subprocess_get_network": "Get network interfaces",
                "subprocess_get_disk_usage": "Get disk usage",
                "subprocess_get_environment": "Get environment variables",
                "subprocess_kill_process": "Kill process",
                "subprocess_list_processes": "List processes"
            }
        }
        
        return actions

    def get_module_status(self) -> Dict[str, Dict[str, Any]]:
        """
        Get status of all action modules.

        Returns:
            Dictionary with module availability and configuration
        """
        status = {
            "files": {
                "available": self.files is not None,
                "description": "File operations (delegates to ActionExecutor)"
            },
            "gui_control": {
                "available": True,  # Always available, may fail if pyautogui missing
                "description": "GUI control using pyautogui"
            },
            "typing": {
                "available": True,  # Always available, may fail if pyautogui missing
                "description": "Text typing using pyautogui"
            },
            "registry": {
                "available": True,  # Always available, Windows-only functionality
                "description": "Windows Registry operations"
            },
            "ocr": {
                "available": True,  # Always available, may fail if dependencies missing
                "description": "OCR using pytesseract/Windows OCR"
            },
            "powershell": {
                "available": True,  # Always available, may fail if PowerShell missing
                "description": "PowerShell command execution"
            },
            "subprocess": {
                "available": True,  # Always available
                "description": "General subprocess operations"
            }
        }
        
        return status


# Export the main classes
__all__ = [
    "SystemActionRouter",
    "ActionResult",
    "FileActions",
    "GUIControlActions", 
    "TypingActions",
    "RegistryActions",
    "OCRActions",
    "PowerShellActions",
    "SubprocessActions"
]