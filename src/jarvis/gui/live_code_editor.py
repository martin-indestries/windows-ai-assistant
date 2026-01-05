"""
Live code editor panel for real-time code viewing with syntax highlighting.
"""

import logging
import re

import customtkinter as ctk

logger = logging.getLogger(__name__)


class LiveCodeEditor(ctk.CTkFrame):
    """
    Real-time code viewer with syntax highlighting.

    Features:
    - CustomTkinter Text widget with Python syntax highlighting
    - Auto-scrolls to bottom as code generates
    - Shows line count and character count
    - Can be toggled on/off
    """

    # Python syntax highlighting colors
    KEYWORD_COLOR = "#FF79C6"  # Pink for keywords
    STRING_COLOR = "#F1FA8C"  # Yellow for strings
    COMMENT_COLOR = "#6272A4"  # Purple for comments
    NUMBER_COLOR = "#BD93F9"  # Purple for numbers
    FUNCTION_COLOR = "#50FA7B"  # Green for functions
    DEFAULT_COLOR = "#F8F8F2"  # White-ish for default text

    # Python keywords to highlight
    KEYWORDS = {
        "def",
        "class",
        "if",
        "elif",
        "else",
        "for",
        "while",
        "break",
        "continue",
        "return",
        "yield",
        "import",
        "from",
        "as",
        "try",
        "except",
        "finally",
        "with",
        "pass",
        "raise",
        "lambda",
        "and",
        "or",
        "not",
        "in",
        "is",
        "True",
        "False",
        "None",
        "async",
        "await",
        "assert",
        "del",
        "global",
        "nonlocal",
        "print",
        "input",
        "range",
        "len",
        "str",
        "int",
        "float",
    }

    def __init__(self, parent_frame, **kwargs):
        """
        Initialize live code editor.

        Args:
            parent_frame: Parent frame to pack into
            **kwargs: Additional frame arguments
        """
        super().__init__(parent_frame, **kwargs)

        self.configure(fg_color=("#2B2B2B", "#1E1E1E"))

        # Title
        self.title_label = ctk.CTkLabel(self, text="📝 GENERATED CODE", font=("Arial", 12, "bold"))
        self.title_label.pack(pady=(5, 0), padx=10, anchor="w")

        # Code count label
        self.count_label = ctk.CTkLabel(
            self, text="0 lines | 0 chars", font=("Arial", 10), text_color="gray"
        )
        self.count_label.pack(pady=(0, 5), padx=10, anchor="w")

        # Code text area with scrollbar
        self.text_frame = ctk.CTkFrame(self, fg_color=("#1E1E1E", "#111111"))
        self.text_frame.pack(fill="both", expand=True, padx=5, pady=5)

        self.scrollbar = ctk.CTkScrollbar(self.text_frame)
        self.scrollbar.pack(side="right", fill="y")

        self.code_text = ctk.CTkTextbox(
            self.text_frame,
            font=("Consolas", 12),
            text_color=self.DEFAULT_COLOR,
            fg_color=("#1E1E1E", "#111111"),
            border_width=0,
            highlightthickness=0,
        )
        self.code_text.pack(side="left", fill="both", expand=True)
        self.code_text.configure(yscrollcommand=self.scrollbar.set)
        self.scrollbar.configure(command=self.code_text.yview)

        # Configure text tags for syntax highlighting
        self._configure_tags()

        logger.info("LiveCodeEditor initialized")

    def _configure_tags(self) -> None:
        """Configure text tags for syntax highlighting."""
        self.code_text.tag_config("keyword", foreground=self.KEYWORD_COLOR)
        self.code_text.tag_config("string", foreground=self.STRING_COLOR)
        self.code_text.tag_config("comment", foreground=self.COMMENT_COLOR)
        self.code_text.tag_config("number", foreground=self.NUMBER_COLOR)
        self.code_text.tag_config("function", foreground=self.FUNCTION_COLOR)

    def clear(self) -> None:
        """Clear the code editor."""
        self.code_text.delete("1.0", "end")
        self._update_count()

    def set_code(self, text: str) -> None:
        """
        Set full code content.

        Args:
            text: Code text to display
        """
        self.clear()
        self._append_text(text, apply_highlight=True)
        self._update_count()

    def append_code(self, text: str) -> None:
        """
        Append text to the editor (for streaming).

        Args:
            text: Text to append
        """
        self._append_text(text, apply_highlight=True)
        self._update_count()

    def _append_text(self, text: str, apply_highlight: bool = True) -> None:
        """
        Append text to the text widget.

        Args:
            text: Text to append
            apply_highlight: Whether to apply syntax highlighting
        """
        # Get current content to find where to apply highlighting
        start_index = self.code_text.index("end-1c")

        # Insert the text
        self.code_text.insert("end", text)

        # Apply syntax highlighting if requested
        if apply_highlight:
            self._highlight_range(start_index, text)

        # Auto-scroll to bottom
        self.code_text.see("end")

    def _highlight_range(self, start_index: str, text: str) -> None:
        """
        Apply syntax highlighting to a range of text.

        Args:
            start_index: Starting index in the text widget
            text: The text to highlight
        """
        lines = text.split("\n")
        current_index = start_index

        for line in lines:
            if not line.strip():
                current_index = self.code_text.index(f"{current_index}+1l")
                continue

            # Highlight keywords
            for keyword in self.KEYWORDS:
                pattern = rf"(?<!\w)({keyword})(?!\w)"
                self._highlight_pattern(current_index, line, pattern, "keyword")

            # Highlight strings (simple pattern)
            string_pattern = r'(".*?"|\'.*?\'|""".*?""")'
            self._highlight_pattern(current_index, line, string_pattern, "string")

            # Highlight comments
            comment_pattern = r"(#.*)$"
            self._highlight_pattern(current_index, line, comment_pattern, "comment")

            # Highlight numbers
            number_pattern = r"\b(\d+\.?\d*)\b"
            self._highlight_pattern(current_index, line, number_pattern, "number")

            # Highlight function definitions
            func_pattern = r"def\s+(\w+)"
            self._highlight_pattern(current_index, line, func_pattern, "function")

            # Move to next line
            current_index = self.code_text.index(f"{current_index}+1l")

    def _highlight_pattern(self, start_index: str, line: str, pattern: str, tag: str) -> None:
        """
        Highlight all matches of a pattern in a line.

        Args:
            start_index: Starting index in text widget
            line: Line content
            pattern: Regex pattern
            tag: Tag name to apply
        """
        for match in re.finditer(pattern, line, re.IGNORECASE):
            match_start = f"{start_index}+{match.start()}c"
            match_end = f"{start_index}+{match.end()}c"
            self.code_text.tag_add(tag, match_start, match_end)

    def _update_count(self) -> None:
        """Update line and character count label."""
        content = self.code_text.get("1.0", "end-1c")
        line_count = len(content.split("\n"))
        char_count = len(content)
        self.count_label.configure(text=f"{line_count} lines | {char_count} chars")

    def get_code(self) -> str:
        """
        Get current code content.

        Returns:
            Code text
        """
        return str(self.code_text.get("1.0", "end-1c"))

    def configure(self, **kwargs) -> None:
        """
        Configure the frame.

        Args:
            **kwargs: Configuration options
        """
        super().configure(**kwargs)
