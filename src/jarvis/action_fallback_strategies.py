"""
Action fallback strategies module for Jarvis.

Provides alternative execution paths and intelligent retry logic
with exponential backoff and strategy rotation.
"""

import logging
import sys
import time
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple

from jarvis.action_executor import ActionResult
from jarvis.execution_verifier import VerificationResult

logger = logging.getLogger(__name__)


class RetryAttempt:
    """Represents a single retry attempt."""

    def __init__(
        self,
        attempt_number: int,
        strategy_name: str,
        action_type: str,
        params: Dict[str, Any],
        action_result: ActionResult,
        verification_result: Optional[VerificationResult] = None,
        timestamp: Optional[float] = None,
    ):
        """
        Initialize retry attempt.

        Args:
            attempt_number: Which attempt number this is (1-based)
            strategy_name: Name of the strategy used
            action_type: Type of action performed
            params: Parameters used for the action
            action_result: Result from action execution
            verification_result: Result from verification (if performed)
            timestamp: Timestamp of the attempt
        """
        self.attempt_number = attempt_number
        self.strategy_name = strategy_name
        self.action_type = action_type
        self.params = params
        self.action_result = action_result
        self.verification_result = verification_result
        self.timestamp = timestamp or time.time()

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "attempt_number": self.attempt_number,
            "strategy_name": self.strategy_name,
            "action_type": self.action_type,
            "params": self.params,
            "action_result": {
                "success": self.action_result.success,
                "message": self.action_result.message,
                "data": self.action_result.data,
                "error": self.action_result.error,
                "execution_time_ms": self.action_result.execution_time_ms,
            },
            "verification_result": (
                self.verification_result.to_dict() if self.verification_result else None
            ),
            "timestamp": self.timestamp,
        }


class FallbackStrategy:
    """Base class for fallback strategies."""

    def __init__(self, name: str, priority: int = 0):
        """
        Initialize fallback strategy.

        Args:
            name: Strategy name
            priority: Priority (higher = tried first)
        """
        self.name = name
        self.priority = priority

    def get_alternative_params(
        self, original_params: Dict[str, Any], attempt_info: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Get alternative parameters for this strategy.

        Args:
            original_params: Original parameters from the failed attempt
            attempt_info: Information about previous attempts

        Returns:
            Modified parameters for retry
        """
        raise NotImplementedError

    def is_applicable(
        self, action_type: str, original_params: Dict[str, Any], error: Optional[str]
    ) -> bool:
        """
        Check if this strategy is applicable for the given situation.

        Args:
            action_type: Type of action
            original_params: Original parameters
            error: Error message from previous attempt

        Returns:
            True if strategy is applicable
        """
        raise NotImplementedError


class ApplicationFallbackStrategy(FallbackStrategy):
    """Fallback strategies for application launches."""

    def __init__(self):
        """Initialize application fallback strategies."""
        super().__init__("application_fallback", priority=10)

        # Mapping of apps to alternatives
        self.app_alternatives = {
            "notepad.exe": ["write.exe", "code.exe", "notepad++.exe"],
            "calc.exe": ["powershell.exe"],  # Can use PowerShell as calculator
            "mspaint.exe": ["mspaint.exe"],  # No good alternative
            "explorer.exe": ["explorer.exe"],  # No alternative
            "cmd.exe": ["powershell.exe", "wt.exe"],
            "powershell.exe": ["cmd.exe", "wt.exe"],
        }

        # Alternative launch methods
        self.launch_methods = ["direct", "explorer", "cmd", "powershell"]

    def get_alternative_params(
        self, original_params: Dict[str, Any], attempt_info: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Get alternative parameters for application launch."""
        app_path = original_params.get("application_path", "")
        attempt_num = attempt_info.get("attempt_number", 1)

        # Strategy 1: Try alternative applications
        if attempt_num == 1:
            alternatives = self.app_alternatives.get(app_path.lower(), [])
            if alternatives:
                return {"application_path": alternatives[0]}

        # Strategy 2: Try alternative launch methods
        launch_method_idx = (attempt_num - 1) % len(self.launch_methods)
        launch_method = self.launch_methods[launch_method_idx]

        if launch_method == "direct":
            return {"application_path": app_path}
        elif launch_method == "explorer":
            return {"application_path": "explorer.exe", "arguments": f'"{app_path}"'}
        elif launch_method == "cmd":
            return {
                "application_path": "cmd.exe",
                "arguments": f'/c start "" "{app_path}"',
            }
        elif launch_method == "powershell":
            return {
                "application_path": "powershell.exe",
                "arguments": f'-Command "Start-Process \\"{app_path}\\""',
            }

        # Fallback: return original params
        return original_params

    def is_applicable(
        self, action_type: str, original_params: Dict[str, Any], error: Optional[str]
    ) -> bool:
        """Check if this strategy is applicable."""
        return action_type.startswith("subprocess_open_application")


class InputFallbackStrategy(FallbackStrategy):
    """Fallback strategies for text input."""

    def __init__(self):
        """Initialize input fallback strategies."""
        super().__init__("input_fallback", priority=10)

        self.input_methods = ["keyboard", "clipboard"]

    def get_alternative_params(
        self, original_params: Dict[str, Any], attempt_info: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Get alternative parameters for text input."""
        attempt_num = attempt_info.get("attempt_number", 1)
        text = original_params.get("text", "")

        # Cycle through input methods
        method_idx = (attempt_num - 1) % len(self.input_methods)
        method = self.input_methods[method_idx]

        if method == "keyboard":
            return {"text": text}
        elif method == "clipboard":
            # This would require using clipboard actions instead of typing
            # For now, we'll return same params
            return {"text": text}

        return original_params

    def is_applicable(
        self, action_type: str, original_params: Dict[str, Any], error: Optional[str]
    ) -> bool:
        """Check if this strategy is applicable."""
        return action_type.startswith("typing_")


class PathFallbackStrategy(FallbackStrategy):
    """Fallback strategies for path-based operations."""

    def __init__(self):
        """Initialize path fallback strategies."""
        super().__init__("path_fallback", priority=10)

        # Alternative locations in order of preference
        self.alternative_locations = [
            Path.home() / "Desktop",
            Path.home() / "Documents",
            Path.home() / "Downloads",
            Path.home() / "Pictures",
            Path.home() / "Music",
            Path.home() / "Videos",
            Path.home(),
            Path("/tmp") if sys.platform != "win32" else Path.home() / "AppData" / "Local" / "Temp",
        ]

    def get_alternative_params(
        self, original_params: Dict[str, Any], attempt_info: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Get alternative parameters for path-based operations."""
        attempt_num = attempt_info.get("attempt_number", 1)

        # Find path parameter
        for key in ["file_path", "directory", "source", "destination"]:
            if key in original_params:
                path_value = original_params[key]
                path_obj = Path(path_value).expanduser().resolve()

                # If path is absolute, try relative or alternative location
                if path_obj.is_absolute():
                    filename = path_obj.name

                    # Try alternative locations
                    location_idx = min(attempt_num, len(self.alternative_locations)) - 1
                    alt_location = self.alternative_locations[location_idx]
                    alt_path = alt_location / filename

                    result = original_params.copy()
                    result[key] = str(alt_path)
                    return result

        # No path parameter found or relative path
        return original_params

    def is_applicable(
        self, action_type: str, original_params: Dict[str, Any], error: Optional[str]
    ) -> bool:
        """Check if this strategy is applicable."""
        # Check if any path parameter is present
        path_keys = ["file_path", "directory", "source", "destination"]
        return any(key in original_params for key in path_keys)


class StrategyExecutor:
    """
    Executes actions with retry logic and strategy rotation.

    Manages retry attempts, exponential backoff, and fallback strategy
    selection.
    """

    def __init__(
        self,
        max_retries: int = 3,
        backoff_base: float = 1.0,
        backoff_multiplier: float = 2.0,
    ):
        """
        Initialize strategy executor.

        Args:
            max_retries: Maximum number of retry attempts
            backoff_base: Base backoff time in seconds
            backoff_multiplier: Multiplier for exponential backoff
        """
        self.max_retries = max_retries
        self.backoff_base = backoff_base
        self.backoff_multiplier = backoff_multiplier

        # Register fallback strategies
        self.strategies = [
            ApplicationFallbackStrategy(),
            InputFallbackStrategy(),
            PathFallbackStrategy(),
        ]

    def execute_with_retry(
        self,
        action_func: Callable,
        action_type: str,
        original_params: Dict[str, Any],
        verify_func: Optional[Callable] = None,
        dry_run: bool = False,
    ) -> Tuple[ActionResult, List[RetryAttempt]]:
        """
        Execute an action with retry logic and fallback strategies.

        Args:
            action_func: Function to execute the action
            action_type: Type of action being executed
            original_params: Original parameters for the action
            verify_func: Optional verification function
            dry_run: Whether this is a dry run

        Returns:
            Tuple of (final ActionResult, list of RetryAttempt objects)
        """
        attempts: List[RetryAttempt] = []
        current_params = original_params.copy()

        for attempt_num in range(1, self.max_retries + 1):
            logger.info(f"========== ATTEMPT {attempt_num}/{self.max_retries} ==========")
            logger.info(f"Action type: {action_type}")
            logger.info(
                f"Strategy: {self._get_strategy_name(attempt_num, action_type, original_params)}"
            )
            logger.info(f"Parameters: {current_params}")

            # Execute the action
            action_result = action_func(**current_params)

            # Verification (if provided and action succeeded)
            verification_result = None
            if verify_func and action_result.success:
                logger.info("Action execution succeeded, verifying...")
                verification_result = verify_func(action_type, action_result, **current_params)

                # If verification passed, we're done
                if verification_result.verified:
                    logger.info("Verification passed, action successful")
                    attempts.append(
                        RetryAttempt(
                            attempt_number=attempt_num,
                            strategy_name=self._get_strategy_name(
                                attempt_num, action_type, original_params
                            ),
                            action_type=action_type,
                            params=current_params.copy(),
                            action_result=action_result,
                            verification_result=verification_result,
                        )
                    )
                    break

                # If verification failed, check if we should retry
                logger.warning(
                    f"Verification failed: {verification_result.error_message}"
                )
                logger.info("Will retry with fallback strategy...")
            elif action_result.success and verify_func is None:
                # Action succeeded and no verification function, we're done
                logger.info("Action execution succeeded (no verification)")
                attempts.append(
                    RetryAttempt(
                        attempt_number=attempt_num,
                        strategy_name=self._get_strategy_name(
                            attempt_num, action_type, original_params
                        ),
                        action_type=action_type,
                        params=current_params.copy(),
                        action_result=action_result,
                        verification_result=None,
                    )
                )
                break

            # Create attempt record
            attempts.append(
                RetryAttempt(
                    attempt_number=attempt_num,
                    strategy_name=self._get_strategy_name(attempt_num, action_type, original_params),
                    action_type=action_type,
                    params=current_params.copy(),
                    action_result=action_result,
                    verification_result=verification_result,
                )
            )

            # Check if we should stop early
            if self._should_stop_early(action_result, verification_result):
                logger.info("Stopping retries early (permanent failure detected)")
                break

            # If this wasn't the last attempt, prepare for retry
            if attempt_num < self.max_retries:
                # Apply backoff delay
                delay = self._calculate_backoff(attempt_num)
                if not dry_run:
                    logger.info(f"Waiting {delay:.1f}s before retry...")
                    time.sleep(delay)

                # Get alternative parameters for next attempt
                current_params = self._get_alternative_params(
                    action_type, original_params, attempts
                )

        # Return final result and all attempts
        final_result = attempts[-1].action_result if attempts else ActionResult(
            success=False,
            action_type=action_type,
            message="No attempts were made",
            error="Internal error in retry logic",
            execution_time_ms=0.0,
        )

        return final_result, attempts

    def _get_strategy_name(
        self, attempt_num: int, action_type: str, original_params: Dict[str, Any]
    ) -> str:
        """Get the name of the strategy for this attempt."""
        if attempt_num == 1:
            return "original"

        # Find applicable strategies
        applicable_strategies = [
            s for s in self.strategies if s.is_applicable(action_type, original_params, None)
        ]

        if not applicable_strategies:
            return f"retry_{attempt_num}"

        strategy = applicable_strategies[0]
        if strategy.name == "application_fallback":
            app_path = original_params.get("application_path", "")
            alternatives = strategy.app_alternatives.get(app_path.lower(), [])
            if attempt_num <= len(alternatives) + 1:
                return f"alt_app_{alternatives[min(attempt_num - 2, len(alternatives) - 1)]}"

            # Launch methods
            methods = strategy.launch_methods
            method_idx = min(
                attempt_num - len(alternatives) - 2, len(methods) - 1
            )
            return f"alt_method_{methods[method_idx]}"

        elif strategy.name == "input_fallback":
            methods = strategy.input_methods
            method_idx = min(attempt_num - 2, len(methods) - 1)
            return f"alt_input_{methods[method_idx]}"

        elif strategy.name == "path_fallback":
            locations = strategy.alternative_locations
            loc_idx = min(attempt_num - 2, len(locations) - 1)
            return f"alt_path_{locations[loc_idx].name}"

        return f"fallback_{attempt_num}"

    def _calculate_backoff(self, attempt_num: int) -> float:
        """
        Calculate exponential backoff delay.

        Args:
            attempt_num: Current attempt number

        Returns:
            Backoff delay in seconds
        """
        return self.backoff_base * (self.backoff_multiplier ** (attempt_num - 1))

    def _should_stop_early(
        self, action_result: ActionResult, verification_result: Optional[VerificationResult]
    ) -> bool:
        """
        Check if we should stop retrying early.

        Args:
            action_result: Result from action execution
            verification_result: Result from verification

        Returns:
            True if we should stop early
        """
        # Stop if action failed with permanent error
        if not action_result.success:
            error_msg = (action_result.error or "").lower()

            # Permanent failure indicators
            permanent_errors = [
                "not found",
                "no such file",
                "permission denied",
                "access denied",
                "not installed",
                "does not exist",
            ]

            if any(err in error_msg for err in permanent_errors):
                logger.info("Permanent failure detected, stopping retries")
                return True

        # Stop if verification failed with permanent error
        if verification_result and not verification_result.verified:
            error_msg = (verification_result.error_message or "").lower()

            permanent_verification_errors = [
                "does not exist",
                "not found",
                "locked",
                "permission denied",
            ]

            if any(err in error_msg for err in permanent_verification_errors):
                logger.info("Permanent verification failure detected, stopping retries")
                return True

        return False

    def _get_alternative_params(
        self,
        action_type: str,
        original_params: Dict[str, Any],
        attempts: List[RetryAttempt],
    ) -> Dict[str, Any]:
        """
        Get alternative parameters for the next retry attempt.

        Args:
            action_type: Type of action
            original_params: Original parameters
            attempts: Previous attempts

        Returns:
            Modified parameters for retry
        """
        attempt_num = len(attempts) + 1
        attempt_info = {"attempt_number": attempt_num, "previous_attempts": attempts}

        # Find applicable strategies
        applicable_strategies = [
            s for s in self.strategies if s.is_applicable(action_type, original_params, None)
        ]

        # Sort by priority (higher first)
        applicable_strategies.sort(key=lambda s: s.priority, reverse=True)

        if applicable_strategies:
            # Use the highest priority applicable strategy
            return applicable_strategies[0].get_alternative_params(original_params, attempt_info)

        # No applicable strategy, return original params
        return original_params


class ExecutionReport:
    """Comprehensive report of execution with retries and fallbacks."""

    def __init__(
        self,
        action_type: str,
        original_params: Dict[str, Any],
        final_result: ActionResult,
        attempts: List[RetryAttempt],
    ):
        """
        Initialize execution report.

        Args:
            action_type: Type of action that was executed
            original_params: Original parameters
            final_result: Final ActionResult
            attempts: List of all retry attempts
        """
        self.action_type = action_type
        self.original_params = original_params
        self.final_result = final_result
        self.attempts = attempts
        self.timestamp = time.time()

    @property
    def successful(self) -> bool:
        """Whether the execution was ultimately successful."""
        return self.final_result.success

    @property
    def verified(self) -> bool:
        """Whether the successful execution was verified."""
        if not self.successful:
            return False
        return (
            self.attempts
            and self.attempts[-1].verification_result
            and self.attempts[-1].verification_result.verified
        )

    @property
    def total_attempts(self) -> int:
        """Total number of attempts made."""
        return len(self.attempts)

    @property
    def strategies_used(self) -> List[str]:
        """List of strategy names used, in order."""
        return [attempt.strategy_name for attempt in self.attempts]

    def get_summary(self) -> Dict[str, Any]:
        """
        Get a summary of the execution report.

        Returns:
            Dictionary with execution summary
        """
        successful_attempts = sum(1 for a in self.attempts if a.action_result.success)
        verified_attempts = sum(
            1
            for a in self.attempts
            if a.verification_result and a.verification_result.verified
        )

        return {
            "action_type": self.action_type,
            "successful": self.successful,
            "verified": self.verified,
            "total_attempts": self.total_attempts,
            "successful_attempts": successful_attempts,
            "verified_attempts": verified_attempts,
            "strategies_used": self.strategies_used,
            "final_message": self.final_result.message,
            "final_error": self.final_result.error,
            "timestamp": self.timestamp,
        }

    def get_detailed_report(self) -> Dict[str, Any]:
        """
        Get a detailed report of the execution.

        Returns:
            Dictionary with full execution details
        """
        summary = self.get_summary()
        summary["original_params"] = self.original_params
        summary["attempts"] = [attempt.to_dict() for attempt in self.attempts]

        # Add diagnostics from failed attempts
        failed_diagnostics = []
        for attempt in self.attempts:
            if attempt.verification_result and not attempt.verification_result.verified:
                failed_diagnostics.append(
                    {
                        "attempt": attempt.attempt_number,
                        "strategy": attempt.strategy_name,
                        "error": attempt.verification_result.error_message,
                        "details": attempt.verification_result.details,
                    }
                )
        summary["failed_diagnostics"] = failed_diagnostics

        # Add recommendations
        summary["recommendations"] = self._generate_recommendations()

        return summary

    def _generate_recommendations(self) -> List[str]:
        """
        Generate recommendations based on execution results.

        Returns:
            List of recommendation strings
        """
        recommendations = []

        if not self.successful:
            recommendations.append("Action failed after all retry attempts")

            # Specific recommendations based on action type
            if "open_application" in self.action_type:
                recommendations.append(
                    "Try manually launching the application to ensure it's installed"
                )
                recommendations.append("Check if the application is in your system PATH")

            elif "file_create" in self.action_type or "file_move" in self.action_type:
                recommendations.append("Check disk space availability on the target drive")
                recommendations.append("Verify you have write permissions to the target directory")
                recommendations.append("Try using a different file location")

            elif "typing" in self.action_type:
                recommendations.append("Ensure the target application window is focused")
                recommendations.append("Check if keyboard input is not blocked")
                recommendations.append("Try using clipboard paste instead of typing")

            # Check for specific error patterns
            for attempt in self.attempts:
                if attempt.verification_result and attempt.verification_result.error_message:
                    error_msg = attempt.verification_result.error_message.lower()

                    if "permission" in error_msg or "access denied" in error_msg:
                        recommendations.append("Run Jarvis with elevated/administrator privileges")
                        break

                    if "disk" in error_msg or "space" in error_msg:
                        recommendations.append("Free up disk space or choose a different location")
                        break

                    if "locked" in error_msg:
                        recommendations.append(
                            "Close the file or application that's using it"
                        )
                        break

        else:
            if not self.verified:
                recommendations.append("Action reported success but could not be verified")
                recommendations.append("Manually verify that the action completed as expected")

            elif self.total_attempts > 1:
                recommendations.append(f"Action succeeded after {self.total_attempts} attempts")
                recommendations.append("Consider investigating why the initial attempts failed")

        return recommendations
