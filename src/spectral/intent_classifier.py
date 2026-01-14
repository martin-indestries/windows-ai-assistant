"""
Intent classifier module for differentiating chat vs. action intents.

Uses heuristics first (imperative verbs, question patterns) and falls back to LLM
classification for ambiguous cases.
"""

import logging
import re
from enum import Enum
from typing import Tuple

logger = logging.getLogger(__name__)


class IntentType(str, Enum):
    """Types of user intents."""

    CHAT = "chat"
    ACTION = "action"
    UNKNOWN = "unknown"
    CASUAL = "casual"
    COMMAND = "command"


class IntentClassifier:
    """
    Classifies user input as chat or action intent.

    Uses heuristics first for fast classification, then falls back to LLM
    classification for ambiguous cases.
    """

    def __init__(self) -> None:
        """Initialize the intent classifier."""
        # Action verbs that indicate commands
        self.action_verbs = {
            "open",
            "create",
            "delete",
            "move",
            "copy",
            "start",
            "stop",
            "run",
            "execute",
            "launch",
            "close",
            "save",
            "load",
            "download",
            "upload",
            "install",
            "uninstall",
            "restart",
            "shutdown",
            "type",
            "click",
            "search",
            "find",
            "list",
            "show",
            "hide",
            "enable",
            "disable",
            "connect",
            "disconnect",
            "send",
            "receive",
            "play",
            "pause",
            "record",
            "capture",
            "screenshot",
            "backup",
            "restore",
            "update",
            "upgrade",
            "downgrade",
            "mount",
            "unmount",
            "format",
            "clean",
            "clear",
            "remove",
            "add",
            "insert",
            "replace",
            "rename",
            "edit",
            "modify",
            "change",
            "switch",
            "toggle",
            "check",
            "test",
            "verify",
            "validate",
            "scan",
            "monitor",
            "track",
            "log",
            "export",
            "import",
            "write",
            "make",
            "build",
            "generate",
            "implement",
            "develop",
            "calculate",
            "compute",
            "solve",
            "parse",
            "process",
        }

        # System action keywords
        self.action_keywords = {
            "file",
            "folder",
            "directory",
            "window",
            "application",
            "program",
            "process",
            "service",
            "registry",
            "settings",
            "configuration",
            "network",
            "connection",
            "internet",
            "wifi",
            "bluetooth",
            "usb",
            "drive",
            "disk",
            "volume",
            "partition",
            "memory",
            "ram",
            "cpu",
            "gpu",
            "screen",
            "display",
            "monitor",
            "mouse",
            "keyboard",
            "camera",
            "microphone",
            "speaker",
            "audio",
            "video",
            "image",
            "picture",
            "photo",
            "document",
            "text",
            "email",
            "message",
            "chat",
            "browser",
            "website",
            "url",
            "link",
            "download",
            "upload",
            "cloud",
            "server",
            "database",
            "table",
            "query",
            "script",
            "command",
            "terminal",
            "console",
            "shell",
            "powershell",
            "batch",
            "shortcut",
            "icon",
            "taskbar",
            "desktop",
            "wallpaper",
            "theme",
            "font",
            "color",
            "resolution",
            "brightness",
            "volume",
            "mute",
            "unmute",
            "code",
            "python",
            "javascript",
            "java",
            "function",
            "class",
        }

        # Chat patterns (questions, greetings, conversational phrases)
        # Use \b word boundaries to prevent partial matches
        self.chat_patterns = [
            r"\b(how|what|why|when|where|who|which)\b",
            r"\b(can you|could you|would you|will you|are you|is it)\b",
            r"\b(explain|describe|summarize|help me|show me|let me know)\b",
            r"\b(how are you|what's up|how do you feel|what do you think|what are you doing)\b",
            r"\b(thank you|thanks|sorry|excuse me)\b",
            r"\b(hello|hi|hey|good morning|good afternoon|good evening|bye|goodbye)\b",
            r"\btell me (a )?(joke|story|about|how)\b",
            r"\bwhat('s| is) your (name|purpose|role)\b",
            r"\bhow can (you|i|help)\b",
            r"\?$",  # Ends with question mark
        ]

        # Compile regex patterns
        # All chat patterns use search now since we added \b word boundaries
        self.chat_search_patterns = [
            re.compile(pattern, re.IGNORECASE) for pattern in self.chat_patterns
        ]

        logger.info("IntentClassifier initialized")

    def classify_heuristic(self, user_input: str) -> Tuple[IntentType, float]:
        """
        Classify intent using heuristics only.

        Args:
            user_input: User input string

        Returns:
            Tuple of (IntentType, confidence_score)
        """
        input_lower = user_input.lower().strip()
        words = input_lower.split()

        # Check for chat patterns first (higher priority)
        for pattern in self.chat_search_patterns:
            if pattern.search(input_lower):
                logger.debug(f"Chat pattern matched: {pattern.pattern}")
                return IntentType.CHAT, 0.9

        # Check for imperative action verbs at the beginning
        if words and words[0] in self.action_verbs:
            logger.debug(f"Action verb detected: {words[0]}")
            return IntentType.ACTION, 0.8

        # Check for action keywords anywhere in the input
        action_keyword_count = sum(1 for word in words if word in self.action_keywords)
        if action_keyword_count >= 2:
            logger.debug(f"Multiple action keywords detected: {action_keyword_count}")
            return IntentType.ACTION, 0.7

        # Check for single action keyword with action verb
        if action_keyword_count >= 1:
            action_verbs_in_input = sum(1 for word in words if word in self.action_verbs)
            if action_verbs_in_input >= 1:
                logger.debug("Action keyword + verb combination detected")
                return IntentType.ACTION, 0.6

        # Check for question mark (strong chat indicator)
        if input_lower.endswith("?"):
            logger.debug("Question mark detected")
            return IntentType.CHAT, 0.8

        # If no strong indicators, return unknown with low confidence
        logger.debug("No strong heuristics matched")
        return IntentType.UNKNOWN, 0.3

    def classify_with_llm(self, user_input: str) -> Tuple[IntentType, float]:
        """
        Classify intent using LLM for ambiguous cases.

        Args:
            user_input: User input string

        Returns:
            Tuple of (IntentType, confidence_score)
        """
        # This would use the Brain server to classify ambiguous intents
        # For now, return a simple heuristic-based classification
        # In a full implementation, this would call the LLM

        input_lower = user_input.lower().strip()

        # Simple keyword-based classification as fallback
        action_like = any(word in self.action_verbs for word in input_lower.split()[:3])
        chat_like = any(pattern.search(input_lower) for pattern in self.chat_search_patterns)

        if action_like and not chat_like:
            return IntentType.ACTION, 0.6
        elif chat_like and not action_like:
            return IntentType.CHAT, 0.6
        else:
            # Default to chat for ambiguous cases (safer)
            return IntentType.CHAT, 0.4

    def classify(self, user_input: str) -> Tuple[IntentType, float]:
        """
        Classify user intent using heuristics first, then LLM fallback.

        Args:
            user_input: User input string

        Returns:
            Tuple of (IntentType, confidence_score)
        """
        logger.debug(f"Classifying intent for: {user_input}")

        # Try heuristic classification first
        intent, confidence = self.classify_heuristic(user_input)

        # If confidence is high enough, use it
        if confidence >= 0.7:
            logger.debug(f"High confidence heuristic classification: {intent} ({confidence})")
            return intent, confidence

        # If heuristics are uncertain, try LLM classification
        logger.debug("Low confidence heuristics, trying LLM classification")
        llm_intent, llm_confidence = self.classify_with_llm(user_input)

        # Use LLM result if it has higher confidence
        if llm_confidence > confidence:
            logger.debug(f"Using LLM classification: {llm_intent} ({llm_confidence})")
            return llm_intent, llm_confidence
        else:
            logger.debug(f"Using heuristic classification: {intent} ({confidence})")
            return intent, confidence

    def is_chat_intent(self, user_input: str) -> bool:
        """
        Check if user input is a chat intent.

        Args:
            user_input: User input string

        Returns:
            True if chat intent, False otherwise
        """
        intent, confidence = self.classify(user_input)
        return intent == IntentType.CHAT

    def is_action_intent(self, user_input: str) -> bool:
        """
        Check if user input is an action intent.

        Args:
            user_input: User input string

        Returns:
            True if action intent, False otherwise
        """
        intent, confidence = self.classify(user_input)
        return intent == IntentType.ACTION

    def classify_intent(self, user_input: str) -> str:
        """
        Classify user input as 'casual' or 'command'.

        This is a convenience method that maps the internal CHAT/ACTION intents
        to the casual/command terminology used in the conversational response system.

        Args:
            user_input: User input string

        Returns:
            "casual" if this is a conversational/greeting input
            "command" if this is an action/task request
        """
        intent, confidence = self.classify(user_input)

        # Map CHAT -> casual, ACTION -> command
        if intent == IntentType.CHAT:
            return "casual"
        elif intent == IntentType.ACTION:
            return "command"
        else:
            # For UNKNOWN intents, default to casual (safer to be conversational)
            logger.debug(f"Unknown intent classified as 'casual' with confidence {confidence}")
            return "casual"
