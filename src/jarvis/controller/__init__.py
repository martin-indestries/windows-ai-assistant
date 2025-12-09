"""
Controller package for the dual-model stack.

Provides planning (brain) and execution (dispatch) capabilities for routing
user intents through BrainServer and ExecutorServer.
"""

from jarvis.controller.brain_server import BrainServer
from jarvis.controller.controller import Controller, ControllerResult
from jarvis.controller.dispatcher import AttemptResult, Dispatcher, RetryPolicy, StepOutcome
from jarvis.controller.executor_server import ExecutorServer
from jarvis.controller.planner import Planner
from jarvis.controller.step_verifier import StepVerifier, VerificationResult

__all__ = [
    "AttemptResult",
    "BrainServer",
    "Controller",
    "ControllerResult",
    "Dispatcher",
    "ExecutorServer",
    "Planner",
    "RetryPolicy",
    "StepOutcome",
    "StepVerifier",
    "VerificationResult",
]
