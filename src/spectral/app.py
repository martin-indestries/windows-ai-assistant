"""
GUI application module using CustomTkinter.

Provides a modern dark-theme GUI with chat transcript streaming,
plan/execution status badges, and integration with the voice interface.
"""

import logging
import threading
import tkinter as tk
from typing import Any, Callable, Optional

import customtkinter

from spectral.chat import ChatSession
from spectral.config import JarvisConfig
from spectral.gui.sandbox_viewer import SandboxViewer
from spectral.intent_classifier import IntentClassifier
from spectral.orchestrator import Orchestrator
from spectral.persistent_memory import MemoryModule
from spectral.reasoning import ReasoningModule
from spectral.response_generator import ResponseGenerator

logger = logging.getLogger(__name__)


class GUIApp(customtkinter.CTk):
    """Main GUI application built with CustomTkinter."""

    def __init__(
        self,
        orchestrator: Orchestrator,
        reasoning_module: Optional[ReasoningModule] = None,
        config: Optional[JarvisConfig] = None,
        voice_callback: Optional[Callable[[], None]] = None,
        dual_execution_orchestrator: Optional[Any] = None,
        memory_module: Optional[MemoryModule] = None,
        sandbox_debug_mode: bool = False,
    ) -> None:
        """
        Initialize the GUI application.

        Args:
            orchestrator: Orchestrator for handling commands
            reasoning_module: Optional reasoning module for planning
            config: Optional configuration
            voice_callback: Optional callback for voice input
            dual_execution_orchestrator: Optional dual execution orchestrator for code execution
            memory_module: Optional memory module for persistent conversation
            sandbox_debug_mode: Enable sandbox viewer debug mode
        """
        super().__init__()

        self.orchestrator = orchestrator
        self.reasoning_module = reasoning_module
        self.config = config or JarvisConfig()
        self.voice_callback = voice_callback
        self.dual_execution_orchestrator = dual_execution_orchestrator
        self.memory_module = memory_module
        self.sandbox_debug_mode = sandbox_debug_mode

        # Initialize intent classifier and response generator
        self.intent_classifier = IntentClassifier()
        self.response_generator = ResponseGenerator()

        # Create chat session
        self.chat_session = ChatSession(
            orchestrator=orchestrator,
            reasoning_module=reasoning_module,
            config=config,
            dual_execution_orchestrator=dual_execution_orchestrator,
            intent_classifier=self.intent_classifier,
            response_generator=self.response_generator,
            memory_module=memory_module,
        )

        # GUI state
        self._processing = False
        self._current_command = ""

        # Configure window
        self.title("Spectral AI Assistant")
        self.geometry("1200x900")

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
        # Main container - split into chat area (top) and sandbox viewer (bottom)
        self.main_frame = customtkinter.CTkFrame(self)
        self.main_frame.pack(side="left", fill="both", expand=True, padx=10, pady=10)

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
        chat_title = customtkinter.CTkLabel(
            self.main_frame, text="Chat", font=("Arial", 14, "bold")
        )
        chat_title.pack(pady=5)

        # Use standard tk.Text instead of CTkTextbox to support tags for coloring
        self.chat_text = tk.Text(
            self.main_frame,
            background=self._get_dark_bg_color(),
            foreground="white",
            insertbackground="white",
            font=("Arial", 11),
            wrap="word",
            state="disabled",
        )
        self.chat_text.pack(fill="both", expand=True, pady=5)
        # Configure tag for user messages (blue color)
        self.chat_text.tag_configure("user_message", foreground="#1E90FF")

        # Plan/Execution status
        status_frame = customtkinter.CTkFrame(self.main_frame)
        status_frame.pack(pady=5, fill="x")

        self.plan_status = customtkinter.CTkLabel(
            status_frame, text="Plan: Idle", font=("Arial", 10), text_color="gray"
        )
        self.plan_status.pack(side="left", padx=5)

        self.exec_status = customtkinter.CTkLabel(
            status_frame, text="Execution: Idle", font=("Arial", 10), text_color="gray"
        )
        self.exec_status.pack(side="left", padx=5)

        # Sandbox viewer toggle button
        self.sandbox_toggle_button = customtkinter.CTkButton(
            status_frame,
            text="📊 Show Sandbox Viewer",
            command=self._toggle_sandbox_viewer,
            width=150,
            font=("Arial", 10),
        )
        self.sandbox_toggle_button.pack(side="right", padx=5)

        # Input area
        input_frame = customtkinter.CTkFrame(self.main_frame)
        input_frame.pack(pady=5, fill="x")

        self.input_text = customtkinter.CTkEntry(
            input_frame, placeholder_text="Enter command or speak 'Spectral...'"
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

        # Sandbox viewer (initially hidden)
        self.sandbox_frame = customtkinter.CTkFrame(
            self.main_frame, fg_color=("#1E1E1E", "#111111")
        )
        self.sandbox_frame.pack(fill="both", expand=True, padx=5, pady=(5, 0))
        self.sandbox_frame.pack_forget()  # Initially hidden

        self.sandbox_viewer = SandboxViewer(self.sandbox_frame, debug_mode=self.sandbox_debug_mode)
        self.sandbox_viewer.pack(fill="both", expand=True)

    def _toggle_sandbox_viewer(self) -> None:
        """Toggle sandbox viewer visibility."""
        if self.sandbox_frame.winfo_viewable():
            self.sandbox_frame.pack_forget()
            self.sandbox_toggle_button.configure(text="📊 Show Sandbox Viewer")
        else:
            self.sandbox_frame.pack(fill="both", expand=True, padx=5, pady=(5, 0))
            self.sandbox_toggle_button.configure(text="📊 Hide Sandbox Viewer")

    def _run_on_ui_thread(self, func: Callable[[], None]) -> None:
        if threading.current_thread() is threading.main_thread():
            func()
            return

        try:
            self.after(0, func)
        except RuntimeError:
            logger.debug("Skipping UI update; GUI likely shutting down")

    def _get_dark_bg_color(self) -> str:
        """
        Get the dark background color matching CustomTkinter theme.

        Returns:
            Hex color string for dark background
        """
        # CustomTkinter dark theme uses #333333 for frames
        return "#333333"

    def get_gui_callback(self) -> Callable[[str, dict[str, Any]], None]:
        """
        Return callback for sandbox execution system.

        Returns:
            Callback function that routes events to sandbox viewer
        """

        def callback(event_type: str, data: dict[str, Any]) -> None:
            if not hasattr(self, "sandbox_viewer"):
                return

            event_type_copy = event_type
            data_copy: dict[str, Any] = dict(data)

            def _dispatch() -> None:
                self.sandbox_viewer.handle_gui_callback(event_type_copy, data_copy)

            self._run_on_ui_thread(_dispatch)

        return callback

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

        # Display user message in chat BEFORE processing
        def show_user_message():
            self.chat_text.configure(state="normal")
            self.chat_text.insert("end", f"[User] {command}\n", "user_message")
            self.chat_text.insert("end", "\n")
            self.chat_text.see("end")
            self.chat_text.configure(state="disabled")

        self._run_on_ui_thread(show_user_message)
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
            # Add AI: prefix before streaming response
            def _add_ai_prefix() -> None:
                self.chat_text.configure(state="normal")
                self.chat_text.insert("end", "AI: ")
                self.chat_text.see("end")
                self.chat_text.configure(state="disabled")

            self._run_on_ui_thread(_add_ai_prefix)

            # Stream command output
            for chunk in self.chat_session.process_command_stream(command):
                chunk_str = str(chunk)

                def _append_chunk(text: str = chunk_str) -> None:
                    self._append_chat_message(text, is_streaming=True)

                self._run_on_ui_thread(_append_chunk)

            # Add newlines after response to separate conversation turns
            def _add_separator() -> None:
                self.chat_text.configure(state="normal")
                self.chat_text.insert("end", "\n\n")
                self.chat_text.see("end")
                self.chat_text.configure(state="disabled")

            self._run_on_ui_thread(_add_separator)

            def mark_complete() -> None:
                self.plan_status.configure(text="Plan: Complete", text_color="green")
                self.exec_status.configure(text="Execution: Complete", text_color="green")

            self._run_on_ui_thread(mark_complete)

        except Exception as e:
            error_msg = f"Error: {str(e)}"

            def _append_error(msg: str = error_msg) -> None:
                self._append_chat_message(msg)

            self._run_on_ui_thread(_append_error)
            logger.exception("Error processing command")

            def mark_error() -> None:
                self.plan_status.configure(text="Plan: Error", text_color="red")
                self.exec_status.configure(text="Execution: Error", text_color="red")

            self._run_on_ui_thread(mark_error)

        finally:
            self._processing = False
            self._current_command = ""

            def reset_controls() -> None:
                self.send_button.configure(state="normal")
                self.cancel_button.configure(state="disabled")

            self._run_on_ui_thread(reset_controls)

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

        def _update() -> None:
            self.memory_status.configure(text=status, text_color="green")

        self._run_on_ui_thread(_update)

    def update_tool_status(self, status: str) -> None:
        """
        Update tool learning status indicator.

        Args:
            status: Status text
        """

        def _update() -> None:
            self.tool_status.configure(text=status, text_color="green")

        self._run_on_ui_thread(_update)

    def add_action(self, action_id: str, action_text: str) -> None:
        """
        Add an action to the active actions display.

        Args:
            action_id: Unique action identifier
            action_text: Description of the action
        """

        def _add() -> None:
            self.actions_text.configure(state="normal")
            self.actions_text.insert("end", f"[{action_id}] {action_text}\n")
            self.actions_text.see("end")
            self.actions_text.configure(state="disabled")

        self._run_on_ui_thread(_add)

    def remove_action(self, action_id: str) -> None:
        """
        Remove an action from active actions display.

        Args:
            action_id: Unique action identifier to remove
        """

        def _remove() -> None:
            self.actions_text.configure(state="normal")
            content = self.actions_text.get("1.0", "end")
            lines = content.split("\n")
            new_lines = [line for line in lines if not line.startswith(f"[{action_id}]")]
            self.actions_text.delete("1.0", "end")
            self.actions_text.insert("1.0", "\n".join(new_lines))
            self.actions_text.configure(state="disabled")

        self._run_on_ui_thread(_remove)

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
        except Exception:
            logger.exception("Error in GUI event loop")
            return 1


def create_gui_app(
    orchestrator: Orchestrator,
    reasoning_module: Optional[ReasoningModule] = None,
    config: Optional[JarvisConfig] = None,
    voice_callback: Optional[Callable[[], None]] = None,
    dual_execution_orchestrator: Optional[Any] = None,
    memory_module: Optional[MemoryModule] = None,
    sandbox_debug_mode: bool = False,
) -> GUIApp:
    """
    Create and return a GUI application instance.

    Args:
        orchestrator: Orchestrator for handling commands
        reasoning_module: Optional reasoning module for planning
        config: Optional configuration
        voice_callback: Optional callback for voice input
        dual_execution_orchestrator: Optional dual execution orchestrator for code execution
        memory_module: Optional memory module for persistent conversation and execution tracking
        sandbox_debug_mode: Enable sandbox viewer debug mode

    Returns:
        Configured GUIApp instance
    """
    return GUIApp(
        orchestrator=orchestrator,
        reasoning_module=reasoning_module,
        config=config,
        voice_callback=voice_callback,
        dual_execution_orchestrator=dual_execution_orchestrator,
        memory_module=memory_module,
        sandbox_debug_mode=sandbox_debug_mode,
    )
