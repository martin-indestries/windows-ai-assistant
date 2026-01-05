"""
Deployment panel for showing successful deployment with file info.
"""

import logging
import os
from pathlib import Path
from typing import Dict, Optional

import customtkinter as ctk

logger = logging.getLogger(__name__)


class DeploymentPanel(ctk.CTkFrame):
    """
    Shows deployment complete with file info.

    Features:
    - Shows deployment success
    - File path and size
    - Timestamp
    - Clickable buttons to open file/folder
    - Copy path to clipboard
    """

    def __init__(self, parent_frame, **kwargs):
        """
        Initialize deployment panel.

        Args:
            parent_frame: Parent frame to pack into
            **kwargs: Additional frame arguments
        """
        super().__init__(parent_frame, **kwargs)

        self.configure(fg_color=("#2B2B2B", "#1E1E1E"))
        self.current_file_path = None

        # Title
        self.title_label = ctk.CTkLabel(self, text="💾 DEPLOYMENT", font=("Arial", 12, "bold"))
        self.title_label.pack(pady=(5, 0), padx=10, anchor="w")

        # Status label
        self.status_label = ctk.CTkLabel(
            self, text="Waiting for deployment...", font=("Arial", 10), text_color="gray"
        )
        self.status_label.pack(pady=(0, 5), padx=10, anchor="w")

        # File info frame
        self.file_info_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.file_info_frame.pack(fill="x", padx=5, pady=2)

        # File path
        self.path_label = ctk.CTkLabel(self.file_info_frame, text="File: -", font=("Arial", 10))
        self.path_label.pack(anchor="w", padx=5)

        # File size
        self.size_label = ctk.CTkLabel(
            self.file_info_frame, text="Size: -", font=("Arial", 10), text_color="gray"
        )
        self.size_label.pack(anchor="w", padx=5)

        # Timestamp
        self.time_label = ctk.CTkLabel(
            self.file_info_frame, text="Created: -", font=("Arial", 10), text_color="gray"
        )
        self.time_label.pack(anchor="w", padx=5)

        # Test results summary
        self.tests_label = ctk.CTkLabel(
            self.file_info_frame, text="Tests: -", font=("Arial", 10), text_color="gray"
        )
        self.tests_label.pack(anchor="w", padx=5, pady=(5, 0))

        # Buttons frame
        self.buttons_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.buttons_frame.pack(fill="x", padx=5, pady=10)

        # Open folder button
        self.folder_button = ctk.CTkButton(
            self.buttons_frame,
            text="📂 Open Folder",
            command=self._open_folder,
            width=120,
            state="disabled",
        )
        self.folder_button.pack(side="left", padx=5)

        # Open file button
        self.file_button = ctk.CTkButton(
            self.buttons_frame,
            text="📄 Open File",
            command=self._open_file,
            width=120,
            state="disabled",
        )
        self.file_button.pack(side="left", padx=5)

        # Copy path button
        self.copy_button = ctk.CTkButton(
            self.buttons_frame,
            text="✂️ Copy Path",
            command=self._copy_path,
            width=120,
            state="disabled",
        )
        self.copy_button.pack(side="left", padx=5)

        logger.info("DeploymentPanel initialized")

    def show_success(
        self, file_path: str, file_size: int, test_results: Dict, timestamp: Optional[str] = None
    ) -> None:
        """
        Show successful deployment.

        Args:
            file_path: Path to deployed file
            file_size: File size in bytes
            test_results: Test results dictionary
            timestamp: Optional timestamp string
        """
        self.current_file_path = file_path

        # Update status
        total = test_results.get("total", 0)
        passed = test_results.get("passed", 0)
        self.status_label.configure(
            text=f"✅ All tests passed ({passed}/{total})", text_color="#50FA7B"
        )

        # Update file info
        self.path_label.configure(text=f"File: {file_path}")

        # Format file size
        if file_size < 1024:
            size_str = f"{file_size} bytes"
        elif file_size < 1024 * 1024:
            size_str = f"{file_size / 1024:.1f} KB"
        else:
            size_str = f"{file_size / (1024 * 1024):.1f} MB"
        self.size_label.configure(text=f"Size: {size_str}")

        # Timestamp
        if timestamp:
            self.time_label.configure(text=f"Created: {timestamp}")
        else:
            from datetime import datetime

            self.time_label.configure(
                text=f"Created: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
            )

        # Test results
        self.tests_label.configure(
            text=f"Tests: {passed}/{total} passed ({test_results.get('success_rate', 0):.0f}%)"
        )

        # Enable buttons
        self.folder_button.configure(state="normal")
        self.file_button.configure(state="normal")
        self.copy_button.configure(state="normal")

    def show_pending(self) -> None:
        """Show pending deployment state."""
        self.status_label.configure(text="Waiting for deployment...", text_color="gray")
        self.path_label.configure(text="File: -")
        self.size_label.configure(text="Size: -")
        self.time_label.configure(text="Created: -")
        self.tests_label.configure(text="Tests: -")

        self.folder_button.configure(state="disabled")
        self.file_button.configure(state="disabled")
        self.copy_button.configure(state="disabled")

        self.current_file_path = None

    def _open_folder(self) -> None:
        """Open file explorer to folder."""
        if not self.current_file_path:
            return

        file_path = Path(self.current_file_path)
        folder_path = str(file_path.parent)

        import platform

        system = platform.system()

        if system == "Windows":
            os.startfile(folder_path)  # type: ignore[attr-defined]
        elif system == "Darwin":  # macOS
            import subprocess

            subprocess.run(["open", folder_path])
        else:  # Linux
            import subprocess

            subprocess.run(["xdg-open", folder_path])

    def _open_file(self) -> None:
        """Open file in default editor."""
        if not self.current_file_path:
            return

        import platform

        system = platform.system()

        if system == "Windows":
            os.startfile(self.current_file_path)  # type: ignore[attr-defined]
        elif system == "Darwin":  # macOS
            import subprocess

            subprocess.run(["open", self.current_file_path])
        else:  # Linux
            import subprocess

            subprocess.run(["xdg-open", self.current_file_path])

    def _copy_path(self) -> None:
        """Copy file path to clipboard."""
        if not self.current_file_path:
            return

        self.clipboard_clear()
        self.clipboard_append(self.current_file_path)
        self.update()

        # Show feedback
        original_text = self.copy_button.cget("text")
        self.copy_button.configure(text="✅ Copied!")
        self.after(1500, lambda: self.copy_button.configure(text=original_text))

    def configure(self, **kwargs) -> None:
        """
        Configure the frame.

        Args:
            **kwargs: Configuration options
        """
        super().configure(**kwargs)
