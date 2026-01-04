#!/usr/bin/env python3
"""
Demonstration of conversational response feature.

Shows how Jarvis now distinguishes between casual conversation and commands,
responding naturally in both cases.
"""

import os
import sys
from jarvis.intent_classifier import IntentClassifier
from jarvis.response_generator import ResponseGenerator

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "src"))


def demo():
    """Demonstrate conversational response feature."""

    print("=" * 70)
    print("JARVIS CONVERSATIONAL RESPONSE FEATURE DEMO")
    print("=" * 70)
    print()
    print("This demo shows how Jarvis now handles both casual conversation")
    print("and commands with natural, appropriate responses.\n")

    # Initialize components
    classifier = IntentClassifier()
    generator = ResponseGenerator()

    # Demo inputs
    demos = [
        {
            "input": "hello how are you",
            "type": "casual conversation",
        },
        {
            "input": "create a file on desktop with contents hello",
            "type": "command",
        },
        {
            "input": "what's your name",
            "type": "casual conversation",
        },
        {
            "input": "write me a python program to print hello world",
            "type": "command",
        },
        {
            "input": "tell me a joke",
            "type": "casual conversation",
        },
        {
            "input": "list files in my documents folder",
            "type": "command",
        },
    ]

    for i, demo in enumerate(demos, 1):
        print(f"\n{'─' * 70}")
        print(f"DEMO {i}: {demo['type'].upper()}")
        print(f"{'─' * 70}")
        print()

        # Show user input
        print(f"👤 User: {demo['input']}")
        print()

        # Classify intent
        intent = classifier.classify_intent(demo["input"])
        print(f"🔍 Intent: {intent.upper()}")
        print()

        # Simulate execution (for commands)
        if intent == "command":
            print("📋 Planning steps...")
            print("  ✓ Plan created")
            print()
            print("▶️ Starting execution...")
            print("  ✓ Execution complete")
            print()

        # Generate response
        execution_result = {"status": "success"} if intent == "command" else ""
        response = generator.generate_response(intent, str(execution_result), demo["input"])

        # Show response
        print(f"💬 Response: {response}")
        print()

    print("=" * 70)
    print("DEMO COMPLETE")
    print("=" * 70)
    print()
    print("Key Features:")
    print("  • Intent classification distinguishes casual vs command")
    print("  • Casual conversation gets friendly, natural responses")
    print("  • Commands get execution summaries")
    print("  • All planning and execution steps remain unchanged")
    print("  • Response appears at the very end with '💬 Response:' label")
    print()


if __name__ == "__main__":
    demo()
