"""
Generation Events module for real-time code streaming.

Provides event bus for emitting code generation events to subscribers
(sandbox UI, file saver, etc.).
"""

import logging
from typing import Callable, Dict, List, Optional
import threading

logger = logging.getLogger(__name__)


class GenerationEventBus:
    """
    Emit code generation events to subscribers (sandbox UI, file saver, etc.).

    Event types:
    - "generation_start": {"prompt": str, "request_id": str}
    - "code_chunk": {"code": str, "chunk_index": int, "request_id": str}
    - "generation_complete": {"final_code": str, "status": str, "request_id": str}
    - "generation_error": {"error": str, "attempt": int, "request_id": str}
    """

    def __init__(self):
        """Initialize generation event bus."""
        self.subscribers: Dict[str, List[Callable]] = {}
        self.lock = threading.Lock()
        logger.info("GenerationEventBus initialized")

    def subscribe(self, event_type: str, callback: Callable) -> None:
        """
        Subscribe to generation events.

        Args:
            event_type: Type of event to subscribe to
            callback: Callback function (event_type: str, data: dict) -> None
        """
        with self.lock:
            if event_type not in self.subscribers:
                self.subscribers[event_type] = []

            self.subscribers[event_type].append(callback)
            logger.debug(f"Subscribed to event: {event_type}")

    def unsubscribe(self, event_type: str, callback: Callable) -> None:
        """
        Unsubscribe from generation events.

        Args:
            event_type: Type of event to unsubscribe from
            callback: Callback function to remove
        """
        with self.lock:
            if event_type in self.subscribers and callback in self.subscribers[event_type]:
                self.subscribers[event_type].remove(callback)
                logger.debug(f"Unsubscribed from event: {event_type}")

    def emit(self, event_type: str, data: dict) -> None:
        """
        Emit event to all subscribers.

        Args:
            event_type: Type of event to emit
            data: Event data dictionary
        """
        if self.lock.acquire(blocking=False):
            # Make a copy of subscribers list to avoid issues if callbacks modify subscriptions
            subscribers_copy = self.subscribers.get(event_type, []).copy()
            self.lock.release()

            for callback in subscribers_copy:
                try:
                    callback(event_type, data)
                except Exception as e:
                    logger.error(f"Error in event callback for {event_type}: {e}")
        else:
            logger.debug(f"Skipping event emission (lock held): {event_type}")

    # Convenience methods for specific events
    def emit_generation_start(self, prompt: str, request_id: str) -> None:
        """Emit generation_start event."""
        self.emit("generation_start", {
            "prompt": prompt,
            "request_id": request_id
        })

    def emit_code_chunk(
        self,
        code: str,
        chunk_index: int,
        request_id: str
    ) -> None:
        """Emit code_chunk event."""
        self.emit("code_chunk", {
            "code": code,
            "chunk_index": chunk_index,
            "request_id": request_id
        })

    def emit_generation_complete(
        self,
        final_code: str,
        status: str,
        request_id: str,
        metadata: Optional[dict] = None
    ) -> None:
        """Emit generation_complete event."""
        data = {
            "final_code": final_code,
            "status": status,
            "request_id": request_id
        }
        if metadata:
            data.update(metadata)
        self.emit("generation_complete", data)

    def emit_generation_error(
        self,
        error: str,
        attempt: int,
        request_id: str
    ) -> None:
        """Emit generation_error event."""
        self.emit("generation_error", {
            "error": error,
            "attempt": attempt,
            "request_id": request_id
        })


# Global event bus instance
_global_event_bus: Optional[GenerationEventBus] = None
_event_bus_lock = threading.Lock()


def get_event_bus() -> GenerationEventBus:
    """
    Get the global event bus instance (singleton pattern).

    Returns:
        Global GenerationEventBus instance
    """
    global _global_event_bus

    if _global_event_bus is None:
        with _event_bus_lock:
            if _global_event_bus is None:
                _global_event_bus = GenerationEventBus()

    return _global_event_bus
