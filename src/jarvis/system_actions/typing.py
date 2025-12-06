"""
Typing system action module.

Provides text typing operations using pyautogui while enforcing
dry-run semantics and safety checks.
"""

import logging
from typing import Optional

try:
    import pyautogui
    import pyperclip
    PYAUTOGUI_AVAILABLE = True
    PYPECLIP_AVAILABLE = True
except ImportError:
    PYAUTOGUI_AVAILABLE = False
    PYPECLIP_AVAILABLE = False

from jarvis.action_executor import ActionResult

logger = logging.getLogger(__name__)


class TypingActions:
    """
    Typing system actions.

    Wraps pyautogui typing operations with dry-run support and safety checks.
    """

    def __init__(self, dry_run: bool = False) -> None:
        """
        Initialize typing actions.

        Args:
            dry_run: If True, preview actions without executing
        """
        self.dry_run = dry_run
        if PYAUTOGUI_AVAILABLE:
            # Set up pyautogui safety
            pyautogui.FAILSAFE = True
            pyautogui.PAUSE = 0.1
        logger.info("TypingActions initialized")

    def type_text(self, text: str, interval: float = 0.01) -> ActionResult:
        """
        Type text using keyboard simulation.

        Args:
            text: Text to type
            interval: Interval between keystrokes in seconds

        Returns:
            ActionResult indicating success or failure
        """
        logger.info(f"Typing text: {repr(text[:50])}...")
        
        if not PYAUTOGUI_AVAILABLE:
            return ActionResult(
                success=False,
                action_type="type_text",
                message="pyautogui not available",
                error="Install pyautogui to use typing features",
                execution_time_ms=0.0
            )

        if self.dry_run:
            return ActionResult(
                success=True,
                action_type="type_text",
                message=f"[DRY-RUN] Would type: {repr(text)}",
                data={"text": text, "interval": interval, "dry_run": True}
            )

        try:
            pyautogui.typewrite(text, interval=interval)
            return ActionResult(
                success=True,
                action_type="type_text",
                message=f"Typed {len(text)} characters",
                data={"text": text, "interval": interval, "length": len(text)}
            )
        except Exception as e:
            logger.error(f"Error typing text: {e}")
            return ActionResult(
                success=False,
                action_type="type_text",
                message="Failed to type text",
                error=str(e)
            )

    def press_key(self, key: str, presses: int = 1) -> ActionResult:
        """
        Press a keyboard key.

        Args:
            key: Key to press (e.g., 'enter', 'space', 'ctrl+c')
            presses: Number of times to press the key

        Returns:
            ActionResult indicating success or failure
        """
        logger.info(f"Pressing key: {key} ({presses} times)")
        
        if not PYAUTOGUI_AVAILABLE:
            return ActionResult(
                success=False,
                action_type="press_key",
                message="pyautogui not available",
                error="Install pyautogui to use typing features"
            )

        if self.dry_run:
            return ActionResult(
                success=True,
                action_type="press_key",
                message=f"[DRY-RUN] Would press {key} {presses} times",
                data={"key": key, "presses": presses, "dry_run": True}
            )

        try:
            pyautogui.press(key, presses=presses)
            return ActionResult(
                success=True,
                action_type="press_key",
                message=f"Pressed {key} {presses} times",
                data={"key": key, "presses": presses}
            )
        except Exception as e:
            logger.error(f"Error pressing key: {e}")
            return ActionResult(
                success=False,
                action_type="press_key",
                message="Failed to press key",
                error=str(e)
            )

    def hotkey(self, *keys: str) -> ActionResult:
        """
        Press a combination of keys (hotkey).

        Args:
            *keys: Keys to press together (e.g., 'ctrl', 'c')

        Returns:
            ActionResult indicating success or failure
        """
        key_combo = '+'.join(keys)
        logger.info(f"Pressing hotkey: {key_combo}")
        
        if not PYAUTOGUI_AVAILABLE:
            return ActionResult(
                success=False,
                action_type="hotkey",
                message="pyautogui not available",
                error="Install pyautogui to use typing features"
            )

        if self.dry_run:
            return ActionResult(
                success=True,
                action_type="hotkey",
                message=f"[DRY-RUN] Would press hotkey: {key_combo}",
                data={"keys": list(keys), "dry_run": True}
            )

        try:
            pyautogui.hotkey(*keys)
            return ActionResult(
                success=True,
                action_type="hotkey",
                message=f"Pressed hotkey: {key_combo}",
                data={"keys": list(keys)}
            )
        except Exception as e:
            logger.error(f"Error pressing hotkey: {e}")
            return ActionResult(
                success=False,
                action_type="hotkey",
                message="Failed to press hotkey",
                error=str(e)
            )

    def copy_to_clipboard(self, text: str) -> ActionResult:
        """
        Copy text to clipboard.

        Args:
            text: Text to copy to clipboard

        Returns:
            ActionResult indicating success or failure
        """
        logger.info(f"Copying text to clipboard: {repr(text[:50])}...")
        
        if not PYPECLIP_AVAILABLE:
            return ActionResult(
                success=False,
                action_type="copy_to_clipboard",
                message="pyperclip not available",
                error="Install pyperclip to use clipboard features"
            )

        if self.dry_run:
            return ActionResult(
                success=True,
                action_type="copy_to_clipboard",
                message=f"[DRY-RUN] Would copy to clipboard: {repr(text)}",
                data={"text": text, "dry_run": True}
            )

        try:
            pyperclip.copy(text)
            return ActionResult(
                success=True,
                action_type="copy_to_clipboard",
                message=f"Copied {len(text)} characters to clipboard",
                data={"text": text, "length": len(text)}
            )
        except Exception as e:
            logger.error(f"Error copying to clipboard: {e}")
            return ActionResult(
                success=False,
                action_type="copy_to_clipboard",
                message="Failed to copy to clipboard",
                error=str(e)
            )

    def paste_from_clipboard(self) -> ActionResult:
        """
        Paste text from clipboard.

        Returns:
            ActionResult with clipboard content or error
        """
        logger.info("Pasting from clipboard")
        
        if not PYPECLIP_AVAILABLE:
            return ActionResult(
                success=False,
                action_type="paste_from_clipboard",
                message="pyperclip not available",
                error="Install pyperclip to use clipboard features"
            )

        if self.dry_run:
            return ActionResult(
                success=True,
                action_type="paste_from_clipboard",
                message="[DRY-RUN] Would paste from clipboard",
                data={"dry_run": True}
            )

        try:
            text = pyperclip.paste()
            return ActionResult(
                success=True,
                action_type="paste_from_clipboard",
                message=f"Pasted {len(text)} characters from clipboard",
                data={"text": text, "length": len(text)}
            )
        except Exception as e:
            logger.error(f"Error pasting from clipboard: {e}")
            return ActionResult(
                success=False,
                action_type="paste_from_clipboard",
                message="Failed to paste from clipboard",
                error=str(e)
            )

    def get_clipboard_content(self) -> ActionResult:
        """
        Get current clipboard content without pasting.

        Returns:
            ActionResult with clipboard content or error
        """
        logger.info("Getting clipboard content")
        
        if not PYPECLIP_AVAILABLE:
            return ActionResult(
                success=False,
                action_type="get_clipboard_content",
                message="pyperclip not available",
                error="Install pyperclip to use clipboard features"
            )

        try:
            text = pyperclip.paste()
            return ActionResult(
                success=True,
                action_type="get_clipboard_content",
                message=f"Retrieved {len(text)} characters from clipboard",
                data={"text": text, "length": len(text)}
            )
        except Exception as e:
            logger.error(f"Error getting clipboard content: {e}")
            return ActionResult(
                success=False,
                action_type="get_clipboard_content",
                message="Failed to get clipboard content",
                error=str(e)
            )