"""
GUI control system action module.

Provides GUI control operations using pyautogui while enforcing
dry-run semantics and safety checks.
"""

import logging
import tempfile
from typing import Optional, Tuple

try:
    import pyautogui
    PYAUTOGUI_AVAILABLE = True
except ImportError:
    PYAUTOGUI_AVAILABLE = False

from jarvis.action_executor import ActionResult

logger = logging.getLogger(__name__)


class GUIControlActions:
    """
    GUI control system actions.

    Wraps pyautogui operations with dry-run support and safety checks.
    """

    def __init__(self, dry_run: bool = False) -> None:
        """
        Initialize GUI control actions.

        Args:
            dry_run: If True, preview actions without executing
        """
        self.dry_run = dry_run
        if PYAUTOGUI_AVAILABLE:
            # Set up pyautogui safety
            pyautogui.FAILSAFE = True
            pyautogui.PAUSE = 0.1
        logger.info("GUIControlActions initialized")

    def get_screen_size(self) -> ActionResult:
        """
        Get the screen size.

        Returns:
            ActionResult with screen dimensions
        """
        logger.info("Getting screen size")
        
        if not PYAUTOGUI_AVAILABLE:
            return ActionResult(
                success=False,
                action_type="get_screen_size",
                message="pyautogui not available",
                error="Install pyautogui to use GUI control features",
                execution_time_ms=0.0
            )

        try:
            width, height = pyautogui.size()
            return ActionResult(
                success=True,
                action_type="get_screen_size",
                message=f"Screen size: {width}x{height}",
                data={"width": width, "height": height}
            )
        except Exception as e:
            logger.error(f"Error getting screen size: {e}")
            return ActionResult(
                success=False,
                action_type="get_screen_size",
                message="Failed to get screen size",
                error=str(e)
            )

    def capture_screen(
        self, region: Optional[Tuple[int, int, int, int]] = None
    ) -> ActionResult:
        """
        Capture a screenshot of the screen or region.

        Args:
            region: Optional (left, top, width, height) tuple for region capture

        Returns:
            ActionResult with screenshot information
        """
        logger.info(f"Capturing screen (region={region})")
        
        if not PYAUTOGUI_AVAILABLE:
            return ActionResult(
                success=False,
                action_type="capture_screen",
                message="pyautogui not available",
                error="Install pyautogui to use GUI control features"
            )

        if self.dry_run:
            return ActionResult(
                success=True,
                action_type="capture_screen",
                message=f"[DRY-RUN] Would capture screen (region={region})",
                data={"region": region, "dry_run": True}
            )

        try:
            with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as tmp:
                if region:
                    screenshot = pyautogui.screenshot(region=region)
                else:
                    screenshot = pyautogui.screenshot()
                screenshot.save(tmp.name)
                
                return ActionResult(
                    success=True,
                    action_type="capture_screen",
                    message=f"Screenshot saved to {tmp.name}",
                    data={"screenshot_path": tmp.name, "region": region, "size": screenshot.size}
                )
        except Exception as e:
            logger.error(f"Error capturing screen: {e}")
            return ActionResult(
                success=False,
                action_type="capture_screen",
                message="Failed to capture screen",
                error=str(e)
            )

    def move_mouse(self, x: int, y: int, duration: float = 0.5) -> ActionResult:
        """
        Move the mouse to specified coordinates.

        Args:
            x: X coordinate
            y: Y coordinate
            duration: Duration of movement in seconds

        Returns:
            ActionResult indicating success or failure
        """
        logger.info(f"Moving mouse to ({x}, {y})")
        
        if not PYAUTOGUI_AVAILABLE:
            return ActionResult(
                success=False,
                action_type="move_mouse",
                message="pyautogui not available",
                error="Install pyautogui to use GUI control features"
            )

        if self.dry_run:
            return ActionResult(
                success=True,
                action_type="move_mouse",
                message=f"[DRY-RUN] Would move mouse to ({x}, {y})",
                data={"x": x, "y": y, "duration": duration, "dry_run": True}
            )

        try:
            pyautogui.moveTo(x, y, duration=duration)
            return ActionResult(
                success=True,
                action_type="move_mouse",
                message=f"Moved mouse to ({x}, {y})",
                data={"x": x, "y": y, "duration": duration}
            )
        except Exception as e:
            logger.error(f"Error moving mouse: {e}")
            return ActionResult(
                success=False,
                action_type="move_mouse",
                message="Failed to move mouse",
                error=str(e)
            )

    def click_mouse(
        self,
        x: Optional[int] = None,
        y: Optional[int] = None,
        button: str = "left",
        clicks: int = 1
    ) -> ActionResult:
        """
        Click the mouse at specified coordinates or current position.

        Args:
            x: Optional X coordinate (if None, uses current position)
            y: Optional Y coordinate (if None, uses current position)
            button: Mouse button ("left", "right", "middle")
            clicks: Number of clicks

        Returns:
            ActionResult indicating success or failure
        """
        logger.info(f"Clicking mouse ({button} button, {clicks} clicks)")
        
        if not PYAUTOGUI_AVAILABLE:
            return ActionResult(
                success=False,
                action_type="click_mouse",
                message="pyautogui not available",
                error="Install pyautogui to use GUI control features"
            )

        if self.dry_run:
            pos = f"({x}, {y})" if x and y else "current position"
            return ActionResult(
                success=True,
                action_type="click_mouse",
                message=f"[DRY-RUN] Would click {button} button {clicks} times at {pos}",
                data={"x": x, "y": y, "button": button, "clicks": clicks, "dry_run": True}
            )

        try:
            if x and y:
                pyautogui.click(x, y, clicks=clicks, button=button)
            else:
                pyautogui.click(clicks=clicks, button=button)
            
            return ActionResult(
                success=True,
                action_type="click_mouse",
                message=f"Clicked {button} button {clicks} times",
                data={"x": x, "y": y, "button": button, "clicks": clicks}
            )
        except Exception as e:
            logger.error(f"Error clicking mouse: {e}")
            return ActionResult(
                success=False,
                action_type="click_mouse",
                message="Failed to click mouse",
                error=str(e)
            )

    def get_mouse_position(self) -> ActionResult:
        """
        Get the current mouse position.

        Returns:
            ActionResult with mouse coordinates
        """
        logger.info("Getting mouse position")
        
        if not PYAUTOGUI_AVAILABLE:
            return ActionResult(
                success=False,
                action_type="get_mouse_position",
                message="pyautogui not available",
                error="Install pyautogui to use GUI control features"
            )

        try:
            x, y = pyautogui.position()
            return ActionResult(
                success=True,
                action_type="get_mouse_position",
                message=f"Mouse position: ({x}, {y})",
                data={"x": x, "y": y}
            )
        except Exception as e:
            logger.error(f"Error getting mouse position: {e}")
            return ActionResult(
                success=False,
                action_type="get_mouse_position",
                message="Failed to get mouse position",
                error=str(e)
            )