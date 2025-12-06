"""
Tests for the system actions modules.

Comprehensive tests covering file operations, GUI control, typing,
registry, OCR, PowerShell, and subprocess actions.
"""

import pytest
import tempfile
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock

from jarvis.action_executor import ActionExecutor, ActionResult
from jarvis.system_actions import (
    SystemActionRouter,
    FileActions,
    GUIControlActions,
    TypingActions,
    RegistryActions,
    OCRActions,
    PowerShellActions,
    SubprocessActions
)


class TestSystemActionRouter:
    """Test the SystemActionRouter class."""

    def test_init(self):
        """Test router initialization."""
        mock_executor = Mock(spec=ActionExecutor)
        router = SystemActionRouter(
            action_executor=mock_executor,
            dry_run=True,
            action_timeout=60
        )
        
        assert router.dry_run is True
        assert router.action_timeout == 60
        assert router.files is not None
        assert router.gui_control is not None
        assert router.typing is not None
        assert router.registry is not None
        assert router.ocr is not None
        assert router.powershell is not None
        assert router.subprocess is not None

    def test_list_available_actions(self):
        """Test listing available actions."""
        router = SystemActionRouter()
        actions = router.list_available_actions()
        
        assert isinstance(actions, dict)
        assert "file" in actions
        assert "gui" in actions
        assert "typing" in actions
        assert "registry" in actions
        assert "ocr" in actions
        assert "powershell" in actions
        assert "subprocess" in actions
        
        # Check specific actions exist
        assert "file_list" in actions["file"]
        assert "gui_click_mouse" in actions["gui"]
        assert "typing_type_text" in actions["typing"]

    def test_get_module_status(self):
        """Test getting module status."""
        router = SystemActionRouter()
        status = router.get_module_status()
        
        assert isinstance(status, dict)
        assert "files" in status
        assert "gui_control" in status
        assert "typing" in status
        assert "registry" in status
        assert "ocr" in status
        assert "powershell" in status
        assert "subprocess" in status

    def test_route_file_actions(self):
        """Test routing file actions."""
        mock_executor = Mock(spec=ActionExecutor)
        mock_executor.list_files.return_value = ActionResult(
            success=True,
            action_type="list_files",
            message="Files listed",
            data={"files": ["test.txt"]}
        )
        
        router = SystemActionRouter(action_executor=mock_executor)
        result = router.route_action("file_list", directory="/tmp", recursive=False)
        
        assert result.success is True
        assert result.action_type == "list_files"
        mock_executor.list_files.assert_called_once_with(directory="/tmp", recursive=False)

    def test_route_gui_actions(self):
        """Test routing GUI actions."""
        router = SystemActionRouter(dry_run=True)
        result = router.route_action("gui_get_screen_size")
        
        assert result.success is True
        assert "DRY-RUN" in result.message

    def test_route_invalid_action(self):
        """Test routing invalid action."""
        router = SystemActionRouter()
        
        with pytest.raises(ValueError, match="Unknown action type"):
            router.route_action("invalid_action")

    def test_route_action_without_executor(self):
        """Test routing file action without executor."""
        router = SystemActionRouter()  # No action_executor provided
        result = router.route_action("file_list", directory="/tmp")
        
        assert result.success is False
        assert "not available" in result.message


class TestFileActions:
    """Test the FileActions class."""

    def test_init(self):
        """Test FileActions initialization."""
        mock_executor = Mock(spec=ActionExecutor)
        actions = FileActions(mock_executor)
        
        assert actions.action_executor == mock_executor

    def test_list_files(self):
        """Test listing files."""
        mock_executor = Mock(spec=ActionExecutor)
        mock_executor.list_files.return_value = ActionResult(
            success=True,
            action_type="list_files",
            message="Files listed",
            data={"files": ["test.txt"]}
        )
        
        actions = FileActions(mock_executor)
        result = actions.list_files("/tmp", recursive=True)
        
        assert result.success is True
        mock_executor.list_files.assert_called_once_with("/tmp", recursive=True)

    def test_get_file_info(self):
        """Test getting file info."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            test_file = Path(tmp_dir) / "test.txt"
            test_file.write_text("test content")
            
            mock_executor = Mock(spec=ActionExecutor)
            mock_executor._check_path_allowed.return_value = True
            
            actions = FileActions(mock_executor)
            result = actions.get_file_info(str(test_file))
            
            assert result.success is True
            assert result.data["name"] == "test.txt"
            assert result.data["size"] == len("test content")

    def test_get_file_info_not_allowed(self):
        """Test getting file info when path not allowed."""
        mock_executor = Mock(spec=ActionExecutor)
        mock_executor._check_path_allowed.return_value = False
        
        actions = FileActions(mock_executor)
        result = actions.get_file_info("/etc/passwd")
        
        assert result.success is False
        assert "not allowed" in result.message


class TestGUIControlActions:
    """Test the GUIControlActions class."""

    @patch('jarvis.system_actions.gui_control.PYAUTOGUI_AVAILABLE', False)
    def test_init_without_pyautogui(self):
        """Test initialization when pyautogui not available."""
        actions = GUIControlActions(dry_run=True)
        assert actions.dry_run is True

    @patch('jarvis.system_actions.gui_control.PYAUTOGUI_AVAILABLE', True)
    @patch('jarvis.system_actions.gui_control.pyautogui')
    def test_get_screen_size(self, mock_pyautogui):
        """Test getting screen size."""
        mock_pyautogui.size.return_value = (1920, 1080)
        
        actions = GUIControlActions()
        result = actions.get_screen_size()
        
        assert result.success is True
        assert result.data["width"] == 1920
        assert result.data["height"] == 1080

    @patch('jarvis.system_actions.gui_control.PYAUTOGUI_AVAILABLE', True)
    @patch('jarvis.system_actions.gui_control.pyautogui')
    def test_move_mouse_dry_run(self, mock_pyautogui):
        """Test moving mouse in dry run mode."""
        actions = GUIControlActions(dry_run=True)
        result = actions.move_mouse(100, 200, duration=0.5)
        
        assert result.success is True
        assert "DRY-RUN" in result.message
        mock_pyautogui.moveTo.assert_not_called()

    @patch('jarvis.system_actions.gui_control.PYAUTOGUI_AVAILABLE', True)
    @patch('jarvis.system_actions.gui_control.pyautogui')
    def test_click_mouse(self, mock_pyautogui):
        """Test clicking mouse."""
        actions = GUIControlActions(dry_run=False)
        result = actions.click_mouse(x=100, y=200, button="left", clicks=2)
        
        assert result.success is True
        mock_pyautogui.click.assert_called_once_with(100, 200, clicks=2, button="left")


class TestTypingActions:
    """Test the TypingActions class."""

    @patch('jarvis.system_actions.typing.PYAUTOGUI_AVAILABLE', False)
    def test_init_without_pyautogui(self):
        """Test initialization when pyautogui not available."""
        actions = TypingActions(dry_run=True)
        assert actions.dry_run is True

    @patch('jarvis.system_actions.typing.PYAUTOGUI_AVAILABLE', True)
    @patch('jarvis.system_actions.typing.pyautogui')
    def test_type_text(self, mock_pyautogui):
        """Test typing text."""
        actions = TypingActions(dry_run=False)
        result = actions.type_text("Hello World", interval=0.02)
        
        assert result.success is True
        mock_pyautogui.typewrite.assert_called_once_with("Hello World", interval=0.02)

    @patch('jarvis.system_actions.typing.PYPECLIP_AVAILABLE', True)
    @patch('jarvis.system_actions.typing.pyperclip')
    def test_copy_to_clipboard(self, mock_pyperclip):
        """Test copying to clipboard."""
        mock_pyperclip.copy.return_value = None
        
        actions = TypingActions(dry_run=False)
        result = actions.copy_to_clipboard("test text")
        
        assert result.success is True
        mock_pyperclip.copy.assert_called_once_with("test text")


class TestRegistryActions:
    """Test the RegistryActions class."""

    @patch('jarvis.system_actions.registry.WINREG_AVAILABLE', False)
    def test_init_without_winreg(self):
        """Test initialization when winreg not available."""
        actions = RegistryActions(dry_run=True)
        assert actions.dry_run is True

    @patch('jarvis.system_actions.registry.WINREG_AVAILABLE', False)
    def test_list_subkeys_not_available(self):
        """Test listing subkeys when winreg not available."""
        actions = RegistryActions()
        result = actions.list_subkeys("HKEY_CURRENT_USER")
        
        assert result.success is False
        assert "not available" in result.message

    @patch('jarvis.system_actions.registry.WINREG_AVAILABLE', True)
    @patch('jarvis.system_actions.registry.winreg')
    def test_list_subkeys_dry_run(self, mock_winreg):
        """Test listing subkeys in dry run mode."""
        actions = RegistryActions(dry_run=True)
        result = actions.list_subkeys("HKEY_CURRENT_USER", "Software")
        
        assert result.success is True
        assert "DRY-RUN" in result.message
        mock_winreg.OpenKey.assert_not_called()


class TestOCRActions:
    """Test the OCRActions class."""

    @patch('jarvis.system_actions.ocr.PYTESSERACT_AVAILABLE', False)
    def test_init_without_pytesseract(self):
        """Test initialization when pytesseract not available."""
        actions = OCRActions(dry_run=True)
        assert actions.dry_run is True

    @patch('jarvis.system_actions.ocr.PYTESSERACT_AVAILABLE', False)
    def test_extract_text_from_image_not_available(self):
        """Test text extraction when pytesseract not available."""
        actions = OCRActions()
        result = actions.extract_text_from_image("test.png")
        
        assert result.success is False
        assert "not available" in result.message

    @patch('jarvis.system_actions.ocr.PYTESSERACT_AVAILABLE', True)
    @patch('jarvis.system_actions.ocr.PYAUTOGUI_AVAILABLE', True)
    @patch('jarvis.system_actions.ocr.pytesseract')
    @patch('jarvis.system_actions.ocr.pyautogui')
    def test_extract_text_from_screen(self, mock_pyautogui, mock_pytesseract):
        """Test extracting text from screen."""
        from PIL import Image
        mock_image = Mock(spec=Image.Image)
        mock_pyautogui.screenshot.return_value = mock_image
        mock_pytesseract.image_to_string.return_value = "extracted text"
        
        actions = OCRActions(dry_run=False)
        result = actions.extract_text_from_screen()
        
        assert result.success is True
        assert result.data["text"] == "extracted text"
        mock_pyautogui.screenshot.assert_called_once()


class TestPowerShellActions:
    """Test the PowerShellActions class."""

    def test_init(self):
        """Test PowerShellActions initialization."""
        actions = PowerShellActions(dry_run=True, timeout=60)
        
        assert actions.dry_run is True
        assert actions.timeout == 60
        assert actions.powershell_cmd is not None

    @patch('jarvis.system_actions.powershell.subprocess')
    def test_execute_command_dry_run(self, mock_subprocess):
        """Test executing command in dry run mode."""
        actions = PowerShellActions(dry_run=True)
        result = actions.execute_command("Get-Process")
        
        assert result.success is True
        assert "DRY-RUN" in result.message
        mock_subprocess.run.assert_not_called()

    @patch('jarvis.system_actions.powershell.subprocess')
    def test_execute_command_success(self, mock_subprocess):
        """Test successful command execution."""
        mock_result = Mock()
        mock_result.returncode = 0
        mock_result.stdout = "output"
        mock_result.stderr = ""
        mock_subprocess.run.return_value = mock_result
        
        actions = PowerShellActions(dry_run=False)
        result = actions.execute_command("Get-Process")
        
        assert result.success is True
        assert result.data["stdout"] == "output"
        mock_subprocess.run.assert_called_once()

    def test_get_system_info(self):
        """Test getting system information."""
        actions = PowerShellActions(dry_run=True)
        result = actions.get_system_info()
        
        assert result.success is True
        assert "DRY-RUN" in result.message


class TestSubprocessActions:
    """Test the SubprocessActions class."""

    def test_init(self):
        """Test SubprocessActions initialization."""
        actions = SubprocessActions(dry_run=True, timeout=60)
        
        assert actions.dry_run is True
        assert actions.timeout == 60

    @patch('jarvis.system_actions.subprocess_actions.subprocess')
    def test_execute_command_dry_run(self, mock_subprocess):
        """Test executing command in dry run mode."""
        actions = SubprocessActions(dry_run=True)
        result = actions.execute_command("echo hello")
        
        assert result.success is True
        assert "DRY-RUN" in result.message
        mock_subprocess.run.assert_not_called()

    @patch('jarvis.system_actions.subprocess_actions.subprocess')
    def test_execute_command_success(self, mock_subprocess):
        """Test successful command execution."""
        mock_result = Mock()
        mock_result.returncode = 0
        mock_result.stdout = "hello\n"
        mock_result.stderr = ""
        mock_subprocess.run.return_value = mock_result
        
        actions = SubprocessActions(dry_run=False)
        result = actions.execute_command("echo hello")
        
        assert result.success is True
        assert result.data["stdout"] == "hello"
        mock_subprocess.run.assert_called_once()

    @patch('jarvis.system_actions.subprocess_actions.subprocess')
    def test_ping_host(self, mock_subprocess):
        """Test pinging a host."""
        mock_result = Mock()
        mock_result.returncode = 0
        mock_subprocess.run.return_value = mock_result
        
        actions = SubprocessActions(dry_run=False)
        result = actions.ping_host("google.com", count=3)
        
        assert result.success is True
        mock_subprocess.run.assert_called_once()

    @patch('jarvis.system_actions.subprocess_actions.sys.platform', 'win32')
    @patch('jarvis.system_actions.subprocess_actions.os')
    @patch('jarvis.system_actions.subprocess_actions.subprocess')
    def test_open_application_windows(self, mock_subprocess, mock_os):
        """Test opening application on Windows."""
        actions = SubprocessActions(dry_run=False)
        result = actions.open_application("notepad.exe")
        
        assert result.success is True
        mock_os.startfile.assert_called_once_with("notepad.exe")


class TestIntegration:
    """Integration tests for system actions."""

    def test_full_workflow(self):
        """Test a full workflow with multiple actions."""
        mock_executor = Mock(spec=ActionExecutor)
        mock_executor.list_files.return_value = ActionResult(
            success=True,
            action_type="list_files",
            message="Files listed",
            data={"files": ["test.txt"]}
        )
        
        router = SystemActionRouter(action_executor=mock_executor, dry_run=True)
        
        # Test file action
        file_result = router.route_action("file_list", directory="/tmp")
        assert file_result.success is True
        
        # Test GUI action
        gui_result = router.route_action("gui_get_screen_size")
        assert gui_result.success is True
        
        # Test PowerShell action
        ps_result = router.route_action("powershell_execute", command="Get-Process")
        assert ps_result.success is True

    def test_error_handling(self):
        """Test error handling in router."""
        router = SystemActionRouter()
        
        # Test invalid action
        with pytest.raises(ValueError):
            router.route_action("invalid_action")
        
        # Test file action without executor
        result = router.route_action("file_list", directory="/tmp")
        assert result.success is False
        assert "not available" in result.message