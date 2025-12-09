"""
Typing system action module.

Provides text typing operations using pyautogui while enforcing
dry-run semantics and safety checks.
"""

import logging
import os
import time

try:
    # Prevent mouseinfo from failing in headless environments
    if not os.environ.get("DISPLAY"):
        os.environ["DISPLAY"] = ":0"

    import pyautogui
    import pyperclip

    PYAUTOGUI_AVAILABLE = True
    PYPECLIP_AVAILABLE = True
except (ImportError, KeyError, Exception):
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
        start_time = time.time()

        if not PYAUTOGUI_AVAILABLE:
            execution_time_ms = int((time.time() - start_time) * 1000)
            return ActionResult(
                success=False,
                action_type="type_text",
                message="pyautogui not available",
                error="Install pyautogui to use typing features",
                execution_time_ms=execution_time_ms,
            )

        if self.dry_run:
            execution_time_ms = int((time.time() - start_time) * 1000)
            return ActionResult(
                success=True,
                action_type="type_text",
                message=f"[DRY-RUN] Would type: {repr(text)}",
                data={"text": text, "interval": interval, "dry_run": True},
                execution_time_ms=execution_time_ms,
            )

        try:
            pyautogui.typewrite(text, interval=interval)
            execution_time_ms = int((time.time() - start_time) * 1000)
            return ActionResult(
                success=True,
                action_type="type_text",
                message=f"Typed {len(text)} characters",
                data={"text": text, "interval": interval, "length": len(text)},
                execution_time_ms=execution_time_ms,
            )
        except Exception as e:
            logger.error(f"Error typing text: {e}")
            execution_time_ms = int((time.time() - start_time) * 1000)
            return ActionResult(
                success=False,
                action_type="type_text",
                message="Failed to type text",
                error=str(e),
                execution_time_ms=execution_time_ms,
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
        start_time = time.time()

        if not PYAUTOGUI_AVAILABLE:
            execution_time_ms = int((time.time() - start_time) * 1000)
            return ActionResult(
                success=False,
                action_type="press_key",
                message="pyautogui not available",
                error="Install pyautogui to use typing features",
                execution_time_ms=execution_time_ms,
            )

        if self.dry_run:
            execution_time_ms = int((time.time() - start_time) * 1000)
            return ActionResult(
                success=True,
                action_type="press_key",
                message=f"[DRY-RUN] Would press {key} {presses} times",
                data={"key": key, "presses": presses, "dry_run": True},
                execution_time_ms=execution_time_ms,
            )

        try:
            pyautogui.press(key, presses=presses)
            execution_time_ms = int((time.time() - start_time) * 1000)
            return ActionResult(
                success=True,
                action_type="press_key",
                message=f"Pressed {key} {presses} times",
                data={"key": key, "presses": presses},
                execution_time_ms=execution_time_ms,
            )
        except Exception as e:
            logger.error(f"Error pressing key: {e}")
            execution_time_ms = int((time.time() - start_time) * 1000)
            return ActionResult(
                success=False,
                action_type="press_key",
                message="Failed to press key",
                error=str(e),
                execution_time_ms=execution_time_ms,
            )

    def hotkey(self, *keys: str) -> ActionResult:
        """
        Press a combination of keys (hotkey).

        Args:
            *keys: Keys to press together (e.g., 'ctrl', 'c')

        Returns:
            ActionResult indicating success or failure
        """
        key_combo = "+".join(keys)
        logger.info(f"Pressing hotkey: {key_combo}")
        start_time = time.time()

        if not PYAUTOGUI_AVAILABLE:
            execution_time_ms = int((time.time() - start_time) * 1000)
            return ActionResult(
                success=False,
                action_type="hotkey",
                message="pyautogui not available",
                error="Install pyautogui to use typing features",
                execution_time_ms=execution_time_ms,
            )

        if self.dry_run:
            execution_time_ms = int((time.time() - start_time) * 1000)
            return ActionResult(
                success=True,
                action_type="hotkey",
                message=f"[DRY-RUN] Would press hotkey: {key_combo}",
                data={"keys": list(keys), "dry_run": True},
                execution_time_ms=execution_time_ms,
            )

        try:
            pyautogui.hotkey(*keys)
            execution_time_ms = int((time.time() - start_time) * 1000)
            return ActionResult(
                success=True,
                action_type="hotkey",
                message=f"Pressed hotkey: {key_combo}",
                data={"keys": list(keys)},
                execution_time_ms=execution_time_ms,
            )
        except Exception as e:
            logger.error(f"Error pressing hotkey: {e}")
            execution_time_ms = int((time.time() - start_time) * 1000)
            return ActionResult(
                success=False,
                action_type="hotkey",
                message="Failed to press hotkey",
                error=str(e),
                execution_time_ms=execution_time_ms,
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
        start_time = time.time()

        if not PYPECLIP_AVAILABLE:
            execution_time_ms = int((time.time() - start_time) * 1000)
            return ActionResult(
                success=False,
                action_type="copy_to_clipboard",
                message="pyperclip not available",
                error="Install pyperclip to use clipboard features",
                execution_time_ms=execution_time_ms,
            )

        if self.dry_run:
            execution_time_ms = int((time.time() - start_time) * 1000)
            return ActionResult(
                success=True,
                action_type="copy_to_clipboard",
                message=f"[DRY-RUN] Would copy to clipboard: {repr(text)}",
                data={"text": text, "dry_run": True},
                execution_time_ms=execution_time_ms,
            )

        try:
            pyperclip.copy(text)
            execution_time_ms = int((time.time() - start_time) * 1000)
            return ActionResult(
                success=True,
                action_type="copy_to_clipboard",
                message=f"Copied {len(text)} characters to clipboard",
                data={"text": text, "length": len(text)},
                execution_time_ms=execution_time_ms,
            )
        except Exception as e:
            logger.error(f"Error copying to clipboard: {e}")
            execution_time_ms = int((time.time() - start_time) * 1000)
            return ActionResult(
                success=False,
                action_type="copy_to_clipboard",
                message="Failed to copy to clipboard",
                error=str(e),
                execution_time_ms=execution_time_ms,
            )

    def paste_from_clipboard(self) -> ActionResult:
        """
        Paste text from clipboard.

        Returns:
            ActionResult with clipboard content or error
        """
        logger.info("Pasting from clipboard")
        start_time = time.time()

        if not PYPECLIP_AVAILABLE:
            execution_time_ms = int((time.time() - start_time) * 1000)
            return ActionResult(
                success=False,
                action_type="paste_from_clipboard",
                message="pyperclip not available",
                error="Install pyperclip to use clipboard features",
                execution_time_ms=execution_time_ms,
            )

        if self.dry_run:
            execution_time_ms = int((time.time() - start_time) * 1000)
            return ActionResult(
                success=True,
                action_type="paste_from_clipboard",
                message="[DRY-RUN] Would paste from clipboard",
                data={"dry_run": True},
                execution_time_ms=execution_time_ms,
            )

        try:
            text = pyperclip.paste()
            execution_time_ms = int((time.time() - start_time) * 1000)
            return ActionResult(
                success=True,
                action_type="paste_from_clipboard",
                message=f"Pasted {len(text)} characters from clipboard",
                data={"text": text, "length": len(text)},
                execution_time_ms=execution_time_ms,
            )
        except Exception as e:
            logger.error(f"Error pasting from clipboard: {e}")
            execution_time_ms = int((time.time() - start_time) * 1000)
            return ActionResult(
                success=False,
                action_type="paste_from_clipboard",
                message="Failed to paste from clipboard",
                error=str(e),
                execution_time_ms=execution_time_ms,
            )

    def get_clipboard_content(self) -> ActionResult:
        """
        Get current clipboard content without pasting.

        Returns:
            ActionResult with clipboard content or error
        """
        logger.info("Getting clipboard content")
        start_time = time.time()

        if not PYPECLIP_AVAILABLE:
            execution_time_ms = int((time.time() - start_time) * 1000)
            return ActionResult(
                success=False,
                action_type="get_clipboard_content",
                message="pyperclip not available",
                error="Install pyperclip to use clipboard features",
                execution_time_ms=execution_time_ms,
            )

        try:
            text = pyperclip.paste()
            execution_time_ms = int((time.time() - start_time) * 1000)
            return ActionResult(
                success=True,
                action_type="get_clipboard_content",
                message=f"Retrieved {len(text)} characters from clipboard",
                data={"text": text, "length": len(text)},
                execution_time_ms=execution_time_ms,
            )
        except Exception as e:
            logger.error(f"Error getting clipboard content: {e}")
            execution_time_ms = int((time.time() - start_time) * 1000)
            return ActionResult(
                success=False,
                action_type="get_clipboard_content",
                message="Failed to get clipboard content",
                error=str(e),
                execution_time_ms=execution_time_ms,
            )
