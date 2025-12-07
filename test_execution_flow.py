#!/usr/bin/env python3
"""Test script to verify action execution flow without requiring LLM."""

import logging
from pathlib import Path

from jarvis.container import Container
from jarvis.reasoning import Plan, PlanStep, SafetyFlag

# Set up detailed logging
logging.basicConfig(level=logging.INFO, format="%(name)s - %(levelname)s - %(message)s")


def test_file_creation():
    """Test file creation with detailed logging."""
    print("\n" + "=" * 60)
    print("TEST: File Creation on Desktop")
    print("=" * 60)

    # Initialize container
    container = Container()
    orchestrator = container.get_orchestrator()

    # Create a manual plan for file creation
    desktop_path = Path.home() / "Desktop"
    print(f"\nDesktop path: {desktop_path}")
    print(f"Desktop exists: {desktop_path.exists()}")

    plan = Plan(
        plan_id="test_plan_file_create",
        user_input="Create a file called test.txt on desktop",
        description="Create a test file on desktop",
        steps=[
            PlanStep(
                step_number=1,
                description="Create file test.txt on desktop",
                required_tools=["file_manager"],
                dependencies=[],
                safety_flags=[SafetyFlag.FILE_MODIFICATION],
                estimated_duration="1 second",
            )
        ],
        is_safe=True,
        generated_at="2025-12-07T00:00:00Z",
    )

    print(f"\nPlan created: {plan.plan_id}")
    print(f"Steps: {len(plan.steps)}")
    for step in plan.steps:
        print(f"  - Step {step.step_number}: {step.description}")
        print(f"    Tools: {step.required_tools}")

    # Execute the plan
    print("\n" + "-" * 60)
    print("EXECUTING PLAN")
    print("-" * 60)

    result = orchestrator.execute_plan(plan)

    print("\n" + "-" * 60)
    print("EXECUTION RESULT")
    print("-" * 60)
    print(f"Status: {result['status']}")
    print(f"Total steps: {result['total_steps']}")
    print(f"Successful steps: {result['successful_steps']}")

    for step_result in result["results"]:
        print(f"\nStep {step_result['step_number']}:")
        print(f"  Success: {step_result['success']}")
        print(f"  Message: {step_result['message']}")
        if step_result.get("action_type"):
            print(f"  Action type: {step_result['action_type']}")
        if step_result.get("params"):
            print(f"  Params: {step_result['params']}")
        if step_result.get("data"):
            print(f"  Data: {step_result['data']}")
        if step_result.get("error"):
            print(f"  Error: {step_result['error']}")

    # Check if file was created
    test_file = desktop_path / "test.txt"
    print("\n" + "-" * 60)
    print(f"File created: {test_file.exists()}")
    if test_file.exists():
        print(f"File path: {test_file}")
        print("✅ FILE CREATION SUCCESSFUL!")
    else:
        print("❌ FILE WAS NOT CREATED")
    print("-" * 60)


def test_weather_query():
    """Test weather query with detailed logging."""
    print("\n" + "=" * 60)
    print("TEST: Weather Query")
    print("=" * 60)

    container = Container()
    orchestrator = container.get_orchestrator()

    plan = Plan(
        plan_id="test_plan_weather",
        user_input="What's the weather in London?",
        description="Get weather information for London",
        steps=[
            PlanStep(
                step_number=1,
                description="Get weather in London",
                required_tools=["weather_api"],
                dependencies=[],
                safety_flags=[SafetyFlag.NETWORK_ACCESS],
                estimated_duration="2 seconds",
            )
        ],
        is_safe=True,
        generated_at="2025-12-07T00:00:00Z",
    )

    print(f"\nPlan created: {plan.plan_id}")

    # Execute the plan
    print("\n" + "-" * 60)
    print("EXECUTING PLAN")
    print("-" * 60)

    result = orchestrator.execute_plan(plan)

    print("\n" + "-" * 60)
    print("EXECUTION RESULT")
    print("-" * 60)
    print(f"Status: {result['status']}")

    for step_result in result["results"]:
        print(f"\nStep {step_result['step_number']}:")
        print(f"  Success: {step_result['success']}")
        print(f"  Message: {step_result['message']}")
        if step_result.get("data"):
            print(f"  Data: {step_result['data']}")


if __name__ == "__main__":
    print("\n" + "#" * 60)
    print("# JARVIS ACTION EXECUTION FLOW TEST")
    print("#" * 60)

    # Test file creation
    test_file_creation()

    # Test weather query
    test_weather_query()

    print("\n" + "#" * 60)
    print("# TESTS COMPLETE")
    print("#" * 60)
