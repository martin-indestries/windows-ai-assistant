"""
Controller package for the dual-model stack.

Provides planning (brain) and execution (dispatch) capabilities for routing
user intents through BrainServer and ExecutorServer.
"""

from jarvis.controller.brain_server import BrainServer
from jarvis.controller.controller import Controller, ControllerResult
from jarvis.controller.dispatcher import Dispatcher, StepOutcome
from jarvis.controller.executor_server import ExecutorServer
from jarvis.controller.planner import Planner

__all__ = [
    "BrainServer",
    "Controller",
    "ControllerResult",
    "Dispatcher",
    "ExecutorServer",
    "Planner",
    "StepOutcome",
]
