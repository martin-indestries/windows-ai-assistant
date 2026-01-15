"""
Sandbox viewer main container for all sandbox visualization panels.

Integrates:
- LiveCodeEditor: Shows code being generated
- ExecutionConsole: Shows program execution output
- TestResultsViewer: Shows test progress and results
- StatusPanel: Shows execution steps and progress
- DeploymentPanel: Shows deployment success
"""

import logging
from typing import Optional

import customtkinter as ctk

from spectral.gui.deployment_panel import DeploymentPanel
from spectral.gui.execution_console import ExecutionConsole
from spectral.gui.live_code_editor import LiveCodeEditor
from spectral.gui.status_panel import StatusPanel
from spectral.gui.test_results_viewer import TestResultsViewer

logger = logging.getLogger(__name__)


class SandboxViewer(ctk.CTkFrame):
    """
    Main container for all sandbox visualization panels.

    Features:
    - All sub-panels integrated in a cohesive layout
    - Event routing based on event_type
    - Real-time updates via gui_callback
    - Collapsible/expandable sections
    """

    # Layout constants
    PANEL_HEIGHT = 200
    MINIMIZED_HEIGHT = 40

    def __init__(self, parent_frame, debug_mode: bool = False, **kwargs):
        """
        Initialize sandbox viewer.

        Args:
            parent_frame: Parent frame to pack into
            debug_mode: Enable debug logging
            **kwargs: Additional frame arguments
        """
        super().__init__(parent_frame, **kwargs)

        self.configure(fg_color=("#1E1E1E", "#111111"))
        self.debug_mode = debug_mode

        # State tracking
        self.is_visible = True
        self.test_id_map: dict[str, str] = {}  # Map test names to viewer test IDs
        self.current_request_id: Optional[str] = None

        # Timer for elapsed time
        self.timer_running = False
        self.timer_thread = None

        # Setup UI
        self._setup_ui()

        logger.info("SandboxViewer initialized")

    def _setup_ui(self) -> None:
        """Set up the UI layout."""
        # Toggle button at top
        self.toggle_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.toggle_frame.pack(fill="x", padx=5, pady=5)

        self.toggle_button = ctk.CTkButton(
            self.toggle_frame,
            text="▼ Hide Sandbox Viewer",
            command=self._toggle_visibility,
            height=30,
            font=("Arial", 11, "bold"),
        )
        self.toggle_button.pack(fill="x", padx=5)

        # Main content frame (shown/hidden)
        self.content_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.content_frame.pack(fill="both", expand=True)

        # Create panels in a grid layout
        self._create_panels()

    def _create_panels(self) -> None:
        """Create all visualization panels."""
        # Top row: Code editor (left) + Status panel (right)
        top_row = ctk.CTkFrame(self.content_frame, fg_color="transparent")
        top_row.pack(fill="both", expand=True, padx=5, pady=2)

        # Code editor - takes 70% width
        self.code_editor = LiveCodeEditor(top_row, width=500, height=200)
        self.code_editor.pack(side="left", fill="both", expand=True, padx=(0, 2))

        # Status panel - takes 30% width
        self.status_panel = StatusPanel(top_row, width=200, height=200)
        self.status_panel.pack(side="right", fill="both", expand=True, padx=(2, 0))

        # Middle row: Execution console (left) + Test results (right)
        middle_row = ctk.CTkFrame(self.content_frame, fg_color="transparent")
        middle_row.pack(fill="both", expand=True, padx=5, pady=2)

        # Execution console - takes 50% width
        self.execution_console = ExecutionConsole(middle_row, width=350, height=200)
        self.execution_console.pack(side="left", fill="both", expand=True, padx=(0, 2))

        # Test results - takes 50% width
        self.test_results = TestResultsViewer(middle_row, width=350, height=200)
        self.test_results.pack(side="right", fill="both", expand=True, padx=(2, 0))

        # Bottom row: Deployment panel
        bottom_row = ctk.CTkFrame(self.content_frame, fg_color="transparent")
        bottom_row.pack(fill="x", padx=5, pady=2)

        self.deployment_panel = DeploymentPanel(bottom_row, height=150)
        self.deployment_panel.pack(fill="x", padx=5, pady=2)

    def _toggle_visibility(self) -> None:
        """Toggle sandbox viewer visibility."""
        self.is_visible = not self.is_visible

        if self.is_visible:
            self.content_frame.pack(fill="both", expand=True)
            self.toggle_button.configure(text="▼ Hide Sandbox Viewer")
        else:
            self.content_frame.pack_forget()
            self.toggle_button.configure(text="▲ Show Sandbox Viewer")

    def handle_gui_callback(self, event_type: str, data: dict) -> None:
        """
        Handle gui_callback events and update panels.

        Args:
            event_type: Type of event
            data: Event data dictionary
        """
        if self.debug_mode:
            logger.debug(f"SandboxViewer received event: {event_type}, data: {data}")

        handlers = {
            # Code events
            "code_generation_started": self._on_code_generation_started,
            "code_chunk_generated": self._on_code_chunk_generated,
            "code_generated": self._on_code_generated,
            "code_generation_complete": self._on_code_generation_complete,
            # Sandbox events
            "sandbox_created": self._on_sandbox_created,
            "sandbox_cleaned": self._on_sandbox_cleaned,
            # Analysis events
            "program_analyzed": self._on_program_analyzed,
            # Prompt events
            "prompts_injected": self._on_prompts_injected,
            # Test events
            "test_cases_generated": self._on_test_cases_generated,
            "test_started": self._on_test_started,
            "test_completed": self._on_test_completed,
            "test_result": self._on_test_result,
            "test_summary": self._on_test_summary,
            # Execution events
            "execution_line": self._on_execution_line,
            "prompt_detected": self._on_prompt_detected,
            "input_sent": self._on_input_sent,
            "test_output": self._on_test_output,
            # Deployment events
            "deployment_started": self._on_deployment_started,
            "deployment_complete": self._on_deployment_complete,
            # Step events
            "step_progress": self._on_step_progress,
            "retry_attempt": self._on_retry_attempt,
            # Error events
            "error_occurred": self._on_error_occurred,
        }

        handler = handlers.get(event_type)
        if handler:
            try:
                handler(data)
            except Exception as e:
                logger.error(f"Error handling event {event_type}: {e}")
        else:
            if self.debug_mode:
                logger.debug(f"No handler for event: {event_type}")

    # Event handlers
    def _on_code_generation_started(self, data: dict) -> None:
        """Handle code generation started."""
        self.code_editor.clear()
        self.execution_console.log_info("Code generation started...")
        self.status_panel.start_timer()

        # Extract request_id if available
        request_id = data.get("request_id")
        if request_id:
            self.current_request_id = request_id
            from datetime import datetime
            self.code_editor.set_metadata(request_id, timestamp=datetime.now().strftime("%H:%M:%S"))

    def _on_code_chunk_generated(self, data: dict) -> None:
        """Handle code chunk generated (for streaming)."""
        chunk = data.get("chunk", "")
        if chunk:
            # Append code with highlight
            self.code_editor.append_code(chunk)
            # Highlight the new chunk
            self.code_editor.highlight_last_chunk(chunk)

    def _on_code_generated(self, data: dict) -> None:
        """Handle code generated."""
        code = data.get("code", "")
        if code:
            # Remove chunk highlights when final code is set
            self.code_editor.dehighlight_last_chunk()

            # Update file path if available
            file_path = data.get("file_path")
            request_id = data.get("request_id", self.current_request_id or "unknown")

            if file_path:
                from datetime import datetime
                self.code_editor.set_metadata(
                    request_id,
                    timestamp=datetime.now().strftime("%H:%M:%S"),
                    file_path=file_path
                )

            line_count = len(code.split("\n"))
            self.execution_console.log_info(f"Code generated ({line_count} lines)")

    def _on_code_generation_complete(self, data: dict) -> None:
        """Handle code generation complete."""
        self.code_editor.dehighlight_last_chunk()
        self.execution_console.log_info("Code generation complete")

    def _on_sandbox_created(self, data: dict) -> None:
        """Handle sandbox created."""
        sandbox_id = data.get("sandbox_id", "unknown")
        self.execution_console.log_info(f"Sandbox created: {sandbox_id}")
        self.status_panel.mark_step_complete(1)

    def _on_sandbox_cleaned(self, data: dict) -> None:
        """Handle sandbox cleaned."""
        self.execution_console.log_info("Sandbox cleaned up")
        self.status_panel.mark_step_complete(7)

    def _on_program_analyzed(self, data: dict) -> None:
        """Handle program analyzed."""
        analysis = data.get("analysis", {})
        program_type = analysis.get("program_type", "unknown")
        self.execution_console.log_info(f"Program type detected: {program_type}")
        self.status_panel.mark_step_complete(2)

    def _on_prompts_injected(self, data: dict) -> None:
        """Handle prompts injected."""
        count = data.get("count", 0)
        code_preview = data.get("code_preview", "")[:100]
        self.execution_console.log_info(f"Prompts injected: {count}")
        if code_preview:
            self.execution_console.log_info(f"Preview: {code_preview}...")
        self.status_panel.mark_step_complete(4)

    def _on_test_cases_generated(self, data: dict) -> None:
        """Handle test cases generated."""
        count = data.get("count", 0)
        tests = data.get("tests", [])

        # Clear previous tests
        self.test_results.clear()
        self.test_id_map.clear()

        # Add new tests
        for test in tests:
            test_id = self.test_results.add_test(
                name=test.get("name", "Unnamed test"),
                inputs=test.get("inputs", []),
                expected=test.get("expected", ""),
            )
            self.test_id_map[test.get("name", "unknown")] = test_id

        self.execution_console.log_info(f"Generated {count} test cases")
        self.status_panel.mark_step_complete(5)

    def _on_test_started(self, data: dict) -> None:
        """Handle test started."""
        test_name = data.get("test_name", "Unknown")
        test_num = data.get("test_num", 0)

        if test_name in self.test_id_map:
            self.test_results.update_test_running(self.test_id_map[test_name])

        self.execution_console.log_info(f"Running test: {test_name} ({test_num})")
        self.status_panel.mark_step_complete(6)

    def _on_test_completed(self, data: dict) -> None:
        """Handle test completed."""
        test_name = data.get("test_name", "Unknown")
        result = data.get("result", {})
        passed = result.get("passed", False)
        output = result.get("output", "")[:100]
        elapsed = result.get("elapsed_time", 0)

        if test_name in self.test_id_map:
            test_id = self.test_id_map[test_name]
            if passed:
                self.test_results.update_test_passed(test_id, output, elapsed)
            else:
                error = result.get("error", "Test failed")
                self.test_results.update_test_failed(test_id, error)

    def _on_test_result(self, data: dict) -> None:
        """Handle test result (from sandbox_execution_system)."""
        test_num = data.get("test_num", 0)
        result = data.get("result", {})

        passed = result.get("passed", False)
        test_name = result.get("test_name", f"Test {test_num}")
        output = result.get("output", "")[:100]
        elapsed = result.get("elapsed_time", 0)

        if passed:
            self.execution_console.log_info(f"✅ {test_name} passed ({elapsed:.2f}s)")
            self.execution_console.log_output(output)
        else:
            self.execution_console.log_error(f"❌ {test_name} failed")

    def _on_test_summary(self, data: dict) -> None:
        """Handle test summary."""
        summary = data.get("summary", {})
        total = summary.get("total_tests", 0)
        passed = summary.get("passed", 0)
        _ = summary.get("failed", 0)  # noqa: F841
        rate = summary.get("success_rate", 0)

        self.execution_console.log_info(f"Tests: {passed}/{total} passed ({rate:.0f}%)")

    def _on_execution_line(self, data: dict) -> None:
        """Handle execution line output."""
        line = data.get("line", "")
        if line:
            self.execution_console.log_line(line)

    def _on_prompt_detected(self, data: dict) -> None:
        """Handle prompt detected."""
        prompt = data.get("prompt", "")
        if prompt:
            self.execution_console.log_prompt(prompt)

    def _on_input_sent(self, data: dict) -> None:
        """Handle input sent to stdin."""
        input_val = data.get("input", "")
        if input_val:
            self.execution_console.log_input(f'Sending: "{input_val}"')

    def _on_test_output(self, data: dict) -> None:
        """Handle test output."""
        output = data.get("output", "")
        if output:
            self.execution_console.log_output(output)

    def _on_deployment_started(self, data: dict) -> None:
        """Handle deployment started."""
        self.execution_console.log_info("Deploying program...")
        self.deployment_panel.show_pending()

    def _on_deployment_complete(self, data: dict) -> None:
        """Handle deployment complete."""
        deployment = data.get("deployment", {})
        file_path = deployment.get("file_path", "")
        file_size = deployment.get("file_size", 0)

        test_results = {
            "total": 0,
            "passed": 0,
            "success_rate": 100.0,
        }

        # Get test results from test viewer
        viewer_summary = self.test_results.get_summary()
        test_results.update(viewer_summary)

        self.deployment_panel.show_success(
            file_path=file_path, file_size=file_size, test_results=test_results
        )

        self.execution_console.log_info(f"Deployed: {file_path}")
        self.status_panel.mark_step_complete(7)

    def _on_step_progress(self, data: dict) -> None:
        """Handle step progress update."""
        step = data.get("step", 0)
        _ = data.get("total", 7)  # noqa: F841
        description = data.get("description", "")

        self.status_panel.set_step(step, description)

    def _on_retry_attempt(self, data: dict) -> None:
        """Handle retry attempt."""
        attempt = data.get("attempt", 1)
        max_attempts = data.get("max_attempts", 10)
        _ = data.get("error", "")  # noqa: F841

        self.status_panel.set_attempt(attempt, max_attempts)
        self.execution_console.log_info(f"Retry attempt {attempt}/{max_attempts}")

    def _on_error_occurred(self, data: dict) -> None:
        """Handle error occurred."""
        error = data.get("error", "")
        self.execution_console.log_error(f"Error: {error}")

    def clear_all(self) -> None:
        """Clear all panels."""
        self.code_editor.clear()
        self.execution_console.clear()
        self.test_results.clear()
        self.deployment_panel.show_pending()
        self.status_panel.reset()
        self.test_id_map.clear()

    def start_timer(self) -> None:
        """Start the elapsed time timer."""
        self.status_panel.start_timer()

    def update_timer(self) -> None:
        """Update elapsed time display."""
        self.status_panel.update_timer()

    def configure(self, **kwargs) -> None:
        """
        Configure the frame.

        Args:
            **kwargs: Configuration options
        """
        super().configure(**kwargs)
