"""
Voice interface implementation for wake-word detection and speech-to-text.

Provides VoiceInterface supporting wake-word detection and STT conversion
with state machine pattern for reliable voice command processing.
"""

import logging
import threading
from enum import Enum
from typing import Callable, Optional

logger = logging.getLogger(__name__)


class VoiceState(Enum):
    """State machine for voice processing."""

    IDLE = "idle"
    LISTENING_FOR_WAKEWORD = "listening_for_wakeword"
    WAKEWORD_DETECTED = "wakeword_detected"
    RECORDING_COMMAND = "recording_command"
    PROCESSING_STT = "processing_stt"
    ERROR = "error"


class VoiceInterface:
    """
    Handles voice input with wake-word detection and speech-to-text.

    Manages the state machine: Idle -> ListeningForWakeword -> WakewordDetected ->
    RecordingCommand -> ProcessingSTT -> Idle
    """

    def __init__(
        self,
        wakeword: str = "jarvis",
        on_wakeword: Optional[Callable[[], None]] = None,
        on_command: Optional[Callable[[str], None]] = None,
        on_error: Optional[Callable[[str], None]] = None,
    ) -> None:
        """
        Initialize voice interface.

        Args:
            wakeword: Wake word to detect (default: "jarvis")
            on_wakeword: Callback when wake word is detected
            on_command: Callback when command is recognized
            on_error: Callback when error occurs
        """
        self.wakeword = wakeword.lower()
        self.on_wakeword = on_wakeword
        self.on_command = on_command
        self.on_error = on_error

        self._state = VoiceState.IDLE
        self._is_active = False
        self._recording = False
        self._thread: Optional[threading.Thread] = None

        # Try to import speech_recognition and other voice dependencies
        self._stt_available = self._check_stt_available()
        self._wakeword_available = self._check_wakeword_available()

        logger.info(
            f"Voice interface initialized. STT: {self._stt_available}, "
            f"Wakeword: {self._wakeword_available}"
        )

    def _check_stt_available(self) -> bool:
        """Check if speech_recognition is available."""
        try:
            import speech_recognition  # noqa: F401
            return True
        except ImportError:
            logger.warning(
                "speech_recognition not installed. Install with: "
                "pip install SpeechRecognition"
            )
            return False

    def _check_wakeword_available(self) -> bool:
        """Check if wake-word detection dependencies are available."""
        try:
            import pvporcupine  # noqa: F401
            return True
        except ImportError:
            logger.warning(
                "pvporcupine not installed. Install with: "
                "pip install pvporcupine"
            )
            return False

    @property
    def state(self) -> VoiceState:
        """Get current voice processing state."""
        return self._state

    @property
    def is_active(self) -> bool:
        """Check if voice interface is actively listening."""
        return self._is_active

    def start(self) -> None:
        """Start listening for wake word."""
        if self._is_active:
            return

        if not self._stt_available or not self._wakeword_available:
            error_msg = (
                "Voice dependencies not installed. "
                "Install with: pip install SpeechRecognition pvporcupine"
            )
            self._set_state(VoiceState.ERROR)
            if self.on_error:
                self.on_error(error_msg)
            logger.error(error_msg)
            return

        self._is_active = True
        self._set_state(VoiceState.LISTENING_FOR_WAKEWORD)
        self._thread = threading.Thread(target=self._listen_loop, daemon=True)
        self._thread.start()
        logger.info("Voice interface started")

    def stop(self) -> None:
        """Stop listening for voice input."""
        self._is_active = False
        self._recording = False
        self._set_state(VoiceState.IDLE)
        logger.info("Voice interface stopped")

    def _set_state(self, new_state: VoiceState) -> None:
        """
        Set the voice processing state.

        Args:
            new_state: New state to transition to
        """
        old_state = self._state
        self._state = new_state
        if old_state != new_state:
            logger.debug(f"Voice state transition: {old_state.value} -> {new_state.value}")

    def _listen_loop(self) -> None:
        """Main listening loop (runs in background thread)."""
        try:
            import speech_recognition as sr

            recognizer = sr.Recognizer()
            recognizer.energy_threshold = 4000

            with sr.Microphone() as source:
                recognizer.adjust_for_ambient_noise(source, duration=1)

                while self._is_active:
                    try:
                        self._set_state(VoiceState.LISTENING_FOR_WAKEWORD)

                        # Listen for audio
                        audio = recognizer.listen(source, timeout=5, phrase_time_limit=10)

                        self._set_state(VoiceState.PROCESSING_STT)

                        # Try to recognize with Google Speech Recognition
                        try:
                            text = recognizer.recognize_google(audio).lower()
                            logger.debug(f"Recognized: {text}")

                            # Check for wake word
                            if self.wakeword in text:
                                self._handle_wakeword_detected()
                                # Extract command after wake word
                                command = text.split(self.wakeword, 1)[-1].strip()
                                if command:
                                    self._handle_command_recognized(command)
                            else:
                                self._set_state(VoiceState.LISTENING_FOR_WAKEWORD)

                        except sr.UnknownValueError:
                            logger.debug("Could not understand audio")
                            self._set_state(VoiceState.LISTENING_FOR_WAKEWORD)

                    except sr.RequestError as e:
                        logger.warning(f"Speech Recognition error: {e}")
                        self._set_state(VoiceState.ERROR)
                        if self.on_error:
                            self.on_error(f"Speech Recognition error: {e}")

                    except Exception as e:
                        logger.debug(f"Listen error: {e}")
                        if self._is_active:
                            self._set_state(VoiceState.LISTENING_FOR_WAKEWORD)

        except Exception as e:
            logger.exception(f"Error in listen loop: {e}")
            self._set_state(VoiceState.ERROR)
            if self.on_error:
                self.on_error(f"Voice interface error: {e}")
            self._is_active = False

    def _handle_wakeword_detected(self) -> None:
        """Handle wake word detection event."""
        self._set_state(VoiceState.WAKEWORD_DETECTED)
        logger.info(f"Wake word '{self.wakeword}' detected!")
        if self.on_wakeword:
            self.on_wakeword()

    def _handle_command_recognized(self, command: str) -> None:
        """
        Handle recognized command.

        Args:
            command: The recognized voice command
        """
        self._set_state(VoiceState.IDLE)
        logger.info(f"Command recognized: {command}")
        if self.on_command:
            self.on_command(command)
        self._set_state(VoiceState.LISTENING_FOR_WAKEWORD)

    def inject_text(self, text: str) -> None:
        """
        Inject text as if it were recognized from voice.

        Useful for testing and debugging.

        Args:
            text: Text to inject
        """
        logger.debug(f"Injecting text: {text}")
        text_lower = text.lower()

        if self.wakeword in text_lower:
            self._handle_wakeword_detected()
            command = text_lower.split(self.wakeword, 1)[-1].strip()
            if command:
                self._handle_command_recognized(command)
        else:
            logger.debug(f"Injected text does not contain wake word '{self.wakeword}'")
