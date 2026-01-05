"""
Test results viewer panel for showing test execution progress and results.
"""

import logging
from typing import Dict

import customtkinter as ctk

logger = logging.getLogger(__name__)


class TestResultsViewer(ctk.CTkFrame):
    """
    Shows test execution progress and results.

    Features:
    - Shows each test with inputs and expected output
    - Real-time status updates (RUNNING → PASSED/FAILED)
    - Shows actual output for debugging
    - Progress indicator (1/3 passed)
    """

    # Status colors
    PENDING_COLOR = "gray"
    RUNNING_COLOR = "yellow"
    PASSED_COLOR = "green"
    FAILED_COLOR = "red"

    # Status icons
    STATUS_ICONS = {
        "pending": "⏳",
        "running": "▶️",
        "passed": "✅",
        "failed": "❌",
    }

    def __init__(self, parent_frame, **kwargs):
        """
        Initialize test results viewer.

        Args:
            parent_frame: Parent frame to pack into
            **kwargs: Additional frame arguments
        """
        super().__init__(parent_frame, **kwargs)

        self.configure(fg_color=("#2B2B2B", "#1E1E1E"))
        self.test_data = {}  # test_id -> test info
        self.test_counter = 0

        # Title
        self.title_label = ctk.CTkLabel(self, text="🧪 TEST RESULTS", font=("Arial", 12, "bold"))
        self.title_label.pack(pady=(5, 0), padx=10, anchor="w")

        # Summary label
        self.summary_label = ctk.CTkLabel(
            self, text="0/0 PASSED (0%)", font=("Arial", 10), text_color="gray"
        )
        self.summary_label.pack(pady=(0, 5), padx=10, anchor="w")

        # Scrollable frame for test results
        self.scrollable_frame = ctk.CTkScrollableFrame(
            self,
            label_text="",
            fg_color=("#1E1E1E", "#111111"),
        )
        self.scrollable_frame.pack(fill="both", expand=True, padx=5, pady=5)

        logger.info("TestResultsViewer initialized")

    def add_test(self, name: str, inputs: list, expected: str) -> str:
        """
        Add a test to the viewer.

        Args:
            name: Test name
            inputs: List of input values
            expected: Expected output description

        Returns:
            test_id for updating later
        """
        self.test_counter += 1
        test_id = f"test_{self.test_counter}"

        # Create frame for this test
        test_frame = ctk.CTkFrame(self.scrollable_frame, fg_color=("#2B2B2B", "#1E1E1E"))
        test_frame.pack(fill="x", pady=3, padx=3)

        # Store test info
        self.test_data[test_id] = {
            "name": name,
            "inputs": inputs,
            "expected": expected,
            "frame": test_frame,
            "status": "pending",
        }

        # Header row
        header_frame = ctk.CTkFrame(test_frame, fg_color="transparent")
        header_frame.pack(fill="x", padx=5, pady=5)

        # Status icon
        status_label = ctk.CTkLabel(
            header_frame, text=self.STATUS_ICONS["pending"], font=("Arial", 12)
        )
        status_label.pack(side="left")
        self.test_data[test_id]["status_label"] = status_label

        # Test name
        name_label = ctk.CTkLabel(
            header_frame, text=f"Test {self.test_counter}: {name}", font=("Arial", 11, "bold")
        )
        name_label.pack(side="left", padx=5)

        # Inputs label
        inputs_label = ctk.CTkLabel(
            test_frame, text=f"Inputs: {inputs}", font=("Arial", 10), text_color="gray"
        )
        inputs_label.pack(anchor="w", padx=10)

        # Expected label
        expected_label = ctk.CTkLabel(
            test_frame, text=f"Expected: {expected}", font=("Arial", 10), text_color="gray"
        )
        expected_label.pack(anchor="w", padx=10)

        # Update summary
        self._update_summary()

        return test_id

    def update_test_running(self, test_id: str) -> None:
        """
        Mark test as running.

        Args:
            test_id: Test identifier
        """
        if test_id not in self.test_data:
            return

        self.test_data[test_id]["status"] = "running"
        self.test_data[test_id]["status_label"].configure(text=self.STATUS_ICONS["running"])

    def update_test_passed(self, test_id: str, output: str, elapsed: float) -> None:
        """
        Mark test as passed.

        Args:
            test_id: Test identifier
            output: Actual output from test
            elapsed: Time taken in seconds
        """
        if test_id not in self.test_data:
            return

        test_info = self.test_data[test_id]
        test_info["status"] = "passed"
        test_info["status_label"].configure(text=self.STATUS_ICONS["passed"])
        test_info["status_label"].configure(text_color=self.PASSED_COLOR)

        # Add output label
        output_label = ctk.CTkLabel(
            test_info["frame"],
            text=f"Output ({elapsed:.2f}s): {output[:100]}",
            font=("Arial", 10),
            text_color=self.PASSED_COLOR,
        )
        output_label.pack(anchor="w", padx=10, pady=(0, 5))

        self._update_summary()

    def update_test_failed(self, test_id: str, error: str) -> None:
        """
        Mark test as failed.

        Args:
            test_id: Test identifier
            error: Error description
        """
        if test_id not in self.test_data:
            return

        test_info = self.test_data[test_id]
        test_info["status"] = "failed"
        test_info["status_label"].configure(text=self.STATUS_ICONS["failed"])
        test_info["status_label"].configure(text_color=self.FAILED_COLOR)

        # Add error label
        error_label = ctk.CTkLabel(
            test_info["frame"],
            text=f"Error: {error[:100]}",
            font=("Arial", 10),
            text_color=self.FAILED_COLOR,
        )
        error_label.pack(anchor="w", padx=10, pady=(0, 5))

        self._update_summary()

    def _update_summary(self) -> None:
        """Update summary label."""
        total = len(self.test_data)
        passed = sum(1 for t in self.test_data.values() if t["status"] == "passed")

        if total > 0:
            rate = (passed / total) * 100
            self.summary_label.configure(
                text=f"{passed}/{total} PASSED ({rate:.0f}%)",
                text_color=self.PASSED_COLOR if passed == total else "gray",
            )
        else:
            self.summary_label.configure(text="0/0 PASSED (0%)")

    def get_summary(self) -> Dict:
        """
        Get test summary.

        Returns:
            Summary dictionary with total, passed, failed, pass_rate
        """
        total = len(self.test_data)
        passed = sum(1 for t in self.test_data.values() if t["status"] == "passed")
        failed = sum(1 for t in self.test_data.values() if t["status"] == "failed")

        return {
            "total": total,
            "passed": passed,
            "failed": failed,
            "pass_rate": (passed / total * 100) if total > 0 else 0,
        }

    def clear(self) -> None:
        """Clear all test results."""
        for test_id in list(self.test_data.keys()):
            test_info = self.test_data[test_id]
            test_info["frame"].destroy()
        self.test_data.clear()
        self.test_counter = 0
        self._update_summary()

    def configure(self, **kwargs) -> None:
        """
        Configure the frame.

        Args:
            **kwargs: Configuration options
        """
        super().configure(**kwargs)
