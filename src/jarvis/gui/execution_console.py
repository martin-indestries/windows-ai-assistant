"""
Execution console panel for live program execution output.
"""

import logging
from datetime import datetime

import customtkinter as ctk

logger = logging.getLogger(__name__)


class ExecutionConsole(ctk.CTkFrame):
    """
    Terminal-like console for live program execution output.

    Features:
    - Color-coded output:
      🔵 `[PROMPT]` in blue
      🟢 `[INPUT ⬇️]` in green
      🟡 `[OUTPUT]` in yellow
      🔴 `[ERROR]` in red
      ⚪ `[LOG]` in white
    - Timestamps for each line
    - Auto-scrolls to show latest
    """

    # Color scheme
    PROMPT_COLOR = "#8BE9FD"  # Cyan/blue for prompts
    INPUT_COLOR = "#50FA7B"  # Green for inputs
    OUTPUT_COLOR = "#F1FA8C"  # Yellow for outputs
    ERROR_COLOR = "#FF5555"  # Red for errors
    INFO_COLOR = "#F8F8F2"  # White-ish for info
    TIMESTAMP_COLOR = "#6272A4"  # Purple for timestamps

    def __init__(self, parent_frame, show_timestamps: bool = True, **kwargs):
        """
        Initialize execution console.

        Args:
            parent_frame: Parent frame to pack into
            show_timestamps: Whether to show timestamps
            **kwargs: Additional frame arguments
        """
        super().__init__(parent_frame, **kwargs)

        self.configure(fg_color=("#2B2B2B", "#1E1E1E"))
        self.show_timestamps = show_timestamps

        # Title
        self.title_label = ctk.CTkLabel(
            self, text="▶️ EXECUTION CONSOLE", font=("Arial", 12, "bold")
        )
        self.title_label.pack(pady=(5, 0), padx=10, anchor="w")

        # Console text area with scrollbar
        self.text_frame = ctk.CTkFrame(self, fg_color=("#1E1E1E", "#111111"))
        self.text_frame.pack(fill="both", expand=True, padx=5, pady=5)

        self.scrollbar = ctk.CTkScrollbar(self.text_frame)
        self.scrollbar.pack(side="right", fill="y")

        self.console_text = ctk.CTkTextbox(
            self.text_frame,
            font=("Consolas", 11),
            text_color=self.INFO_COLOR,
            fg_color=("#1E1E1E", "#111111"),
            border_width=0,
            highlightthickness=0,
        )
        self.console_text.pack(side="left", fill="both", expand=True)
        self.console_text.configure(yscrollcommand=self.scrollbar.set)
        self.scrollbar.configure(command=self.console_text.yview)

        # Configure tags
        self._configure_tags()

        logger.info("ExecutionConsole initialized")

    def _configure_tags(self) -> None:
        """Configure text tags for different log types."""
        self.console_text.tag_config("prompt", foreground=self.PROMPT_COLOR)
        self.console_text.tag_config("input", foreground=self.INPUT_COLOR)
        self.console_text.tag_config("output", foreground=self.OUTPUT_COLOR)
        self.console_text.tag_config("error", foreground=self.ERROR_COLOR)
        self.console_text.tag_config("info", foreground=self.INFO_COLOR)
        self.console_text.tag_config("timestamp", foreground=self.TIMESTAMP_COLOR)

    def _get_timestamp(self) -> str:
        """Get current timestamp string."""
        if not self.show_timestamps:
            return ""
        now = datetime.now().strftime("%H:%M:%S")
        return f"[{now}] "

    def _log(self, message: str, tag: str, prefix: str = "") -> None:
        """
        Log a message with the given tag.

        Args:
            message: Message to log
            tag: Tag name to apply
            prefix: Optional prefix (e.g., "[PROMPT]")
        """
        timestamp = self._get_timestamp()
        full_message = f"{timestamp}{prefix} {message}\n"

        self.console_text.insert("end", full_message, tag)
        self.console_text.see("end")

    def log_prompt(self, text: str) -> None:
        """
        Log prompt (blue).

        Args:
            text: Prompt text
        """
        self._log(text, "prompt", "[PROMPT]")

    def log_input(self, text: str) -> None:
        """
        Log input sent (green).

        Args:
            text: Input text
        """
        self._log(text, "input", "[INPUT ⬇️]")

    def log_output(self, text: str) -> None:
        """
        Log program output (yellow).

        Args:
            text: Output text
        """
        self._log(text, "output", "[OUTPUT]")

    def log_error(self, text: str) -> None:
        """
        Log error (red).

        Args:
            text: Error text
        """
        self._log(text, "error", "[ERROR]")

    def log_info(self, text: str) -> None:
        """
        Log info (white).

        Args:
            text: Info text
        """
        self._log(text, "info", "[LOG]")

    def log_line(self, line: str) -> None:
        """
        Log a raw line without any formatting.

        Args:
            line: Line to log
        """
        timestamp = self._get_timestamp()
        full_line = f"{timestamp}{line}\n"
        self.console_text.insert("end", full_line)
        self.console_text.see("end")

    def clear(self) -> None:
        """Clear the console."""
        self.console_text.delete("1.0", "end")

    def scroll_to_bottom(self) -> None:
        """Auto-scroll to show latest output."""
        self.console_text.see("end")

    def get_content(self) -> str:
        """
        Get console content.

        Returns:
            Console text
        """
        return str(self.console_text.get("1.0", "end-1c"))

    def configure(self, **kwargs) -> None:
        """
        Configure the frame.

        Args:
            **kwargs: Configuration options
        """
        super().configure(**kwargs)
