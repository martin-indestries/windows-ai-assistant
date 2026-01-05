"""
Status panel for showing execution progress and status.
"""

import logging

import customtkinter as ctk

logger = logging.getLogger(__name__)


class StatusPanel(ctk.CTkFrame):
    """
    Shows execution progress and status.

    Features:
    - Shows all 7 steps of execution
    - Visual indicators: ✅ (done), ⏳ (in progress), ⏸️ (pending)
    - Current step highlighted
    - Elapsed time counter
    - Retry counter
    """

    # Status icons
    DONE_ICON = "✅"
    IN_PROGRESS_ICON = "⏳"
    PENDING_ICON = "⏸️"
    ERROR_ICON = "❌"

    # Execution steps
    STEPS = [
        ("Sandbox Created", "sandbox_created"),
        ("Code Generated", "code_generated"),
        ("Code Cleaned", "code_cleaned"),
        ("Prompts Injected", "prompts_injected"),
        ("Tests Generated", "tests_generated"),
        ("Executing Tests", "executing_tests"),
        ("Deploying Program", "deploying"),
    ]

    def __init__(self, parent_frame, **kwargs):
        """
        Initialize status panel.

        Args:
            parent_frame: Parent frame to pack into
            **kwargs: Additional frame arguments
        """
        super().__init__(parent_frame, **kwargs)

        self.configure(fg_color=("#2B2B2B", "#1E1E1E"))
        self.step_status = {step[0]: "pending" for step in self.STEPS}
        self.start_time = None

        # Title
        self.title_label = ctk.CTkLabel(
            self, text="📊 EXECUTION STATUS", font=("Arial", 12, "bold")
        )
        self.title_label.pack(pady=(5, 0), padx=10, anchor="w")

        # Steps frame
        self.steps_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.steps_frame.pack(fill="x", padx=5, pady=5)

        # Create step labels
        self.step_labels = {}
        for step_name, _ in self.STEPS:
            step_frame = ctk.CTkFrame(self.steps_frame, fg_color="transparent")
            step_frame.pack(fill="x", pady=1)

            icon_label = ctk.CTkLabel(step_frame, text=self.PENDING_ICON, font=("Arial", 10))
            icon_label.pack(side="left", padx=5)

            step_label = ctk.CTkLabel(step_frame, text=step_name, font=("Arial", 10))
            step_label.pack(side="left")

            self.step_labels[step_name] = icon_label

        # Info frame
        self.info_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.info_frame.pack(fill="x", padx=5, pady=5)

        # Elapsed time
        self.elapsed_label = ctk.CTkLabel(
            self.info_frame, text="Elapsed: 0.0s", font=("Arial", 10), text_color="gray"
        )
        self.elapsed_label.pack(side="left", padx=10)

        # Attempt count
        self.attempt_label = ctk.CTkLabel(
            self.info_frame, text="Attempt: 0/0", font=("Arial", 10), text_color="gray"
        )
        self.attempt_label.pack(side="left", padx=10)

        logger.info("StatusPanel initialized")

    def set_step(self, step_num: int, description: str) -> None:
        """
        Set current step (1-indexed).

        Args:
            step_num: Step number (1-based)
            description: Step description
        """
        if step_num < 1 or step_num > len(self.STEPS):
            return

        step_name = self.STEPS[step_num - 1][0]

        # Update icon to in-progress
        self.step_labels[step_name].configure(text=self.IN_PROGRESS_ICON)

        # Highlight current step
        for name, label in self.step_labels.items():
            if name == step_name:
                label.configure(text_color="yellow")
            elif self.step_status.get(name) == "done":
                label.configure(text_color=self._get_done_color())
            else:
                label.configure(text_color="gray")

    def mark_step_complete(self, step_num: int) -> None:
        """
        Mark step as complete.

        Args:
            step_num: Step number (1-based)
        """
        if step_num < 1 or step_num > len(self.STEPS):
            return

        step_name = self.STEPS[step_num - 1][0]
        self.step_status[step_name] = "done"
        self.step_labels[step_name].configure(
            text=self.DONE_ICON, text_color=self._get_done_color()
        )

    def mark_step_error(self, step_num: int) -> None:
        """
        Mark step as error.

        Args:
            step_num: Step number (1-based)
        """
        if step_num < 1 or step_num > len(self.STEPS):
            return

        step_name = self.STEPS[step_num - 1][0]
        self.step_status[step_name] = "error"
        self.step_labels[step_name].configure(text=self.ERROR_ICON, text_color="red")

    def set_status(self, status: str) -> None:
        """
        Set overall status.

        Args:
            status: Status string (generating, testing, deploying, etc.)
        """
        # Could be used for additional status display
        pass

    def set_elapsed_time(self, seconds: float) -> None:
        """
        Update elapsed time.

        Args:
            seconds: Elapsed time in seconds
        """
        self.elapsed_label.configure(text=f"Elapsed: {seconds:.1f}s")

    def set_attempt(self, attempt: int, max_attempts: int) -> None:
        """
        Show retry count.

        Args:
            attempt: Current attempt number
            max_attempts: Maximum attempts
        """
        self.attempt_label.configure(text=f"Attempt: {attempt}/{max_attempts}")

    def start_timer(self) -> None:
        """Start the elapsed time counter."""
        import time

        self.start_time = time.time()

    def update_timer(self) -> None:
        """Update elapsed time display."""
        import time

        if self.start_time:
            elapsed = time.time() - self.start_time
            self.set_elapsed_time(elapsed)

    def reset(self) -> None:
        """Reset status panel to initial state."""
        self.start_time = None
        self.step_status = {step[0]: "pending" for step in self.STEPS}

        for step_name, label in self.step_labels.items():
            label.configure(text=self.PENDING_ICON, text_color="gray")

        self.elapsed_label.configure(text="Elapsed: 0.0s")
        self.attempt_label.configure(text="Attempt: 0/0")

    def _get_done_color(self) -> str:
        """Get color for completed steps."""
        return "#50FA7B"  # Green

    def configure(self, **kwargs) -> None:
        """
        Configure the frame.

        Args:
            **kwargs: Configuration options
        """
        super().configure(**kwargs)
