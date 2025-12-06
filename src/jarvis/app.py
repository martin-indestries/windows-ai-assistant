"""
GUI application module using CustomTkinter.

Provides a modern dark-theme GUI with chat transcript streaming,
plan/execution status badges, and integration with the voice interface.
"""

import logging
import threading
import tkinter as tk
from typing import Any, Callable, Dict, List, Optional

import customtkinter

from jarvis.chat import ChatMessage, ChatSession
from jarvis.config import JarvisConfig
from jarvis.orchestrator import Orchestrator
from jarvis.reasoning import Plan, ReasoningModule

logger = logging.getLogger(__name__)


class GUIApp(customtkinter.CTk):
    """Main GUI application built with CustomTkinter."""

    def __init__(
        self,
        orchestrator: Orchestrator,
        reasoning_module: Optional[ReasoningModule] = None,
        config: Optional[JarvisConfig] = None,
        voice_callback: Optional[Callable[[str], None]] = None,
    ) -> None:
        """
        Initialize the GUI application.

        Args:
            orchestrator: Orchestrator for handling commands
            reasoning_module: Optional reasoning module for planning
            config: Optional configuration
            voice_callback: Optional callback for voice input
        """
        super().__init__()

        self.orchestrator = orchestrator
        self.reasoning_module = reasoning_module
        self.config = config or JarvisConfig()
        self.voice_callback = voice_callback

        # Create chat session
        self.chat_session = ChatSession(
            orchestrator=orchestrator,
            reasoning_module=reasoning_module,
            config=config,
        )

        # GUI state
        self._processing = False
        self._current_command = ""

        # Configure window
        self.title("Jarvis AI Assistant")
        self.geometry("1200x800")

        # Set theme
        theme = "dark"
        if self.config and hasattr(self.config, "gui") and isinstance(self.config.gui, dict):
            theme = self.config.gui.get("theme", "dark")
        customtkinter.set_appearance_mode(theme)
        customtkinter.set_default_color_theme("blue")

        # Setup UI
        self._setup_ui()

        logger.info("GUI application initialized")

    def _setup_ui(self) -> None:
        """Set up the user interface layout."""
        # Main container
        main_frame = customtkinter.CTkFrame(self)
        main_frame.pack(side="left", fill="both", expand=True, padx=10, pady=10)

        # Sidebar
        sidebar_frame = customtkinter.CTkFrame(self, width=250, corner_radius=10)
        sidebar_frame.pack(side="right", fill="both", padx=10, pady=10)
        sidebar_frame.pack_propagate(False)

        # Sidebar title
        sidebar_title = customtkinter.CTkLabel(
            sidebar_frame, text="Status & Actions", font=("Arial", 14, "bold")
        )
        sidebar_title.pack(pady=10)

        # Memory indicator
        memory_frame = customtkinter.CTkFrame(sidebar_frame)
        memory_frame.pack(pady=5, padx=10, fill="x")
        memory_label = customtkinter.CTkLabel(memory_frame, text="📚 Memory:", font=("Arial", 10))
        memory_label.pack(side="left")
        self.memory_status = customtkinter.CTkLabel(
            memory_frame, text="Ready", font=("Arial", 10), text_color="gray"
        )
        self.memory_status.pack(side="right")

        # Tool learning indicator
        tool_frame = customtkinter.CTkFrame(sidebar_frame)
        tool_frame.pack(pady=5, padx=10, fill="x")
        tool_label = customtkinter.CTkLabel(tool_frame, text="🔧 Tools:", font=("Arial", 10))
        tool_label.pack(side="left")
        self.tool_status = customtkinter.CTkLabel(
            tool_frame, text="Loaded", font=("Arial", 10), text_color="gray"
        )
        self.tool_status.pack(side="right")

        # Active actions
        actions_label = customtkinter.CTkLabel(
            sidebar_frame, text="Active Actions:", font=("Arial", 12, "bold")
        )
        actions_label.pack(pady=10)
        self.actions_text = customtkinter.CTkTextbox(
            sidebar_frame, height=200, width=230, text_color="gray"
        )
        self.actions_text.pack(pady=5, padx=5, fill="both", expand=True)
        self.actions_text.configure(state="disabled")

        # Chat area
        chat_title = customtkinter.CTkLabel(main_frame, text="Chat", font=("Arial", 14, "bold"))
        chat_title.pack(pady=5)

        self.chat_text = customtkinter.CTkTextbox(main_frame, text_color="white")
        self.chat_text.pack(fill="both", expand=True, pady=5)
        self.chat_text.configure(state="disabled")

        # Plan/Execution status
        status_frame = customtkinter.CTkFrame(main_frame)
        status_frame.pack(pady=5, fill="x")

        self.plan_status = customtkinter.CTkLabel(
            status_frame, text="Plan: Idle", font=("Arial", 10), text_color="gray"
        )
        self.plan_status.pack(side="left", padx=5)

        self.exec_status = customtkinter.CTkLabel(
            status_frame, text="Execution: Idle", font=("Arial", 10), text_color="gray"
        )
        self.exec_status.pack(side="left", padx=5)

        # Input area
        input_frame = customtkinter.CTkFrame(main_frame)
        input_frame.pack(pady=5, fill="x")

        self.input_text = customtkinter.CTkEntry(
            input_frame, placeholder_text="Enter command or speak 'Jarvis...'"
        )
        self.input_text.pack(side="left", fill="both", expand=True, padx=5)
        self.input_text.bind("<Return>", lambda e: self._send_command())

        self.send_button = customtkinter.CTkButton(
            input_frame, text="Send", command=self._send_command, width=80
        )
        self.send_button.pack(side="left", padx=5)

        self.voice_button = customtkinter.CTkButton(
            input_frame, text="🎤", command=self._toggle_voice, width=50
        )
        self.voice_button.pack(side="left", padx=2)

        self.cancel_button = customtkinter.CTkButton(
            input_frame, text="Cancel", command=self._cancel_command, width=80, state="disabled"
        )
        self.cancel_button.pack(side="left", padx=5)

    def _send_command(self) -> None:
        """Send the input command for processing."""
        if self._processing:
            return

        command = self.input_text.get().strip()
        if not command:
            return

        self.input_text.delete(0, tk.END)
        self._process_command(command)

    def _process_command(self, command: str) -> None:
        """
        Process a command in a background thread.

        Args:
            command: The command to process
        """
        if self._processing:
            return

        self._processing = True
        self._current_command = command
        self.send_button.configure(state="disabled")
        self.cancel_button.configure(state="normal")
        self.plan_status.configure(text="Plan: Processing...", text_color="yellow")
        self.exec_status.configure(text="Execution: Waiting...", text_color="yellow")

        # Run in background thread
        thread = threading.Thread(target=self._command_thread, args=(command,), daemon=True)
        thread.start()

    def _command_thread(self, command: str) -> None:
        """
        Background thread for processing commands.

        Args:
            command: The command to process
        """
        try:
            # Stream command output
            full_response = ""
            for chunk in self.chat_session.process_command_stream(command):
                full_response += chunk
                self._append_chat_message(chunk, is_streaming=True)

            # Update status
            self.plan_status.configure(text="Plan: Complete", text_color="green")
            self.exec_status.configure(text="Execution: Complete", text_color="green")

        except Exception as e:
            error_msg = f"Error: {str(e)}"
            self._append_chat_message(error_msg)
            logger.exception("Error processing command")
            self.plan_status.configure(text="Plan: Error", text_color="red")
            self.exec_status.configure(text="Execution: Error", text_color="red")

        finally:
            self._processing = False
            self.send_button.configure(state="normal")
            self.cancel_button.configure(state="disabled")
            self._current_command = ""

    def _append_chat_message(self, text: str, is_streaming: bool = False) -> None:
        """
        Append text to the chat display.

        Args:
            text: Text to append
            is_streaming: Whether this is streaming output
        """
        self.chat_text.configure(state="normal")
        self.chat_text.insert("end", text)
        self.chat_text.see("end")
        self.chat_text.configure(state="disabled")

    def _toggle_voice(self) -> None:
        """Toggle voice input mode."""
        if self.voice_callback:
            self.voice_callback()
            self.voice_button.configure(text="🎤 Listening...")

    def _cancel_command(self) -> None:
        """Cancel the current command processing."""
        self._processing = False
        self._current_command = ""
        self.send_button.configure(state="normal")
        self.cancel_button.configure(state="disabled")
        self.plan_status.configure(text="Plan: Cancelled", text_color="orange")
        self.exec_status.configure(text="Execution: Cancelled", text_color="orange")

    def update_memory_status(self, status: str) -> None:
        """
        Update memory status indicator.

        Args:
            status: Status text
        """
        self.memory_status.configure(text=status, text_color="green")

    def update_tool_status(self, status: str) -> None:
        """
        Update tool learning status indicator.

        Args:
            status: Status text
        """
        self.tool_status.configure(text=status, text_color="green")

    def add_action(self, action_id: str, action_text: str) -> None:
        """
        Add an action to the active actions display.

        Args:
            action_id: Unique action identifier
            action_text: Description of the action
        """
        self.actions_text.configure(state="normal")
        self.actions_text.insert("end", f"[{action_id}] {action_text}\n")
        self.actions_text.see("end")
        self.actions_text.configure(state="disabled")

    def remove_action(self, action_id: str) -> None:
        """
        Remove an action from active actions display.

        Args:
            action_id: Unique action identifier to remove
        """
        self.actions_text.configure(state="normal")
        content = self.actions_text.get("1.0", "end")
        lines = content.split("\n")
        new_lines = [line for line in lines if not line.startswith(f"[{action_id}]")]
        self.actions_text.delete("1.0", "end")
        self.actions_text.insert("1.0", "\n".join(new_lines))
        self.actions_text.configure(state="disabled")

    def run(self) -> int:
        """
        Run the GUI application.

        Returns:
            Exit code
        """
        try:
            logger.info("Starting GUI event loop")
            self.mainloop()
            return 0
        except Exception as e:
            logger.exception("Error in GUI event loop")
            return 1


def create_gui_app(
    orchestrator: Orchestrator,
    reasoning_module: Optional[ReasoningModule] = None,
    config: Optional[JarvisConfig] = None,
    voice_callback: Optional[Callable[[str], None]] = None,
) -> GUIApp:
    """
    Create and return a GUI application instance.

    Args:
        orchestrator: Orchestrator for handling commands
        reasoning_module: Optional reasoning module for planning
        config: Optional configuration
        voice_callback: Optional callback for voice input

    Returns:
        Configured GUIApp instance
    """
    return GUIApp(
        orchestrator=orchestrator,
        reasoning_module=reasoning_module,
        config=config,
        voice_callback=voice_callback,
    )
