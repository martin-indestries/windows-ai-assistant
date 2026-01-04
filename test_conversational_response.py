#!/usr/bin/env python3
"""Test script for conversational response feature."""

import os
import sys
from jarvis.intent_classifier import IntentClassifier
from jarvis.response_generator import ResponseGenerator

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "src"))


def test_intent_classifier():
    """Test intent classifier with various inputs."""
    print("=" * 60)
    print("Testing Intent Classifier")
    print("=" * 60)

    classifier = IntentClassifier()

    test_cases = [
        ("hello how are you", "casual"),
        ("how are you doing", "casual"),
        ("what's your name", "casual"),
        ("tell me a joke", "casual"),
        ("good morning", "casual"),
        ("how can you help me", "casual"),
        ("create a file on desktop with contents hello", "command"),
        ("write me a python program", "command"),
        ("list files in my documents", "command"),
        ("calculate 2+2", "command"),
    ]

    print("\nTest Results:")
    all_passed = True

    for input_text, expected in test_cases:
        result = classifier.classify_intent(input_text)
        status = "✓" if result == expected else "✗"
        print(f"{status} Input: {input_text!r}")
        print(f"   Expected: {expected}, Got: {result}")

        if result != expected:
            all_passed = False

    print()
    return all_passed


def test_response_generator():
    """Test response generator."""
    print("=" * 60)
    print("Testing Response Generator")
    print("=" * 60)

    generator = ResponseGenerator()

    # Test casual responses
    print("\nCasual Conversation Responses:")
    casual_inputs = [
        "hello how are you",
        "what's your name",
        "how can you help me",
        "tell me a joke",
    ]

    for input_text in casual_inputs:
        response = generator.generate_response("casual", "", input_text)
        print(f"  Input: {input_text!r}")
        print(f"  Response: {response}")
        print()

    # Test command responses
    print("Command Responses:")
    command_inputs = [
        ("create a file on desktop with contents hello", "success"),
        ("write me a python program", "success"),
    ]

    for input_text, status in command_inputs:
        execution_result = f'{{"status": "{status}", "message": "Task completed"}}'
        response = generator.generate_response("command", execution_result, input_text)
        print(f"  Input: {input_text!r}")
        print(f"  Response: {response}")
        print()

    return True


def test_clean_code():
    """Test code cleaning utility."""
    print("=" * 60)
    print("Testing Code Cleaning")
    print("=" * 60)

    from jarvis.utils import clean_code

    test_cases = [
        ("```python\nprint('hello')\n```", "print('hello')"),
        ("```\nprint('world')\n```", "print('world')"),
        ("print('no backticks')", "print('no backticks')"),
        ("```python\n# Comment\ndef foo():\n    pass\n```", "# Comment\ndef foo():\n    pass"),
    ]

    print("\nTest Results:")
    all_passed = True

    for input_code, expected in test_cases:
        result = clean_code(input_code)
        status = "✓" if result == expected else "✗"
        input_preview = repr(input_code)[:50] + "..." if len(input_code) > 50 else repr(input_code)
        print(f"{status} Input: {input_preview}")
        print(f"   Expected: {expected!r}")
        print(f"   Got: {result!r}")

        if result != expected:
            all_passed = False

    print()
    return all_passed


def main():
    """Run all tests."""
    print("\n" + "=" * 60)
    print("CONVERSATIONAL RESPONSE FEATURE TESTS")
    print("=" * 60 + "\n")

    results = {
        "Intent Classifier": test_intent_classifier(),
        "Response Generator": test_response_generator(),
        "Code Cleaning": test_clean_code(),
    }

    print("=" * 60)
    print("TEST SUMMARY")
    print("=" * 60)

    for test_name, passed in results.items():
        status = "✓ PASSED" if passed else "✗ FAILED"
        print(f"{status} - {test_name}")

    all_passed = all(results.values())

    if all_passed:
        print("\n✓ All tests passed!")
        return 0
    else:
        print("\n✗ Some tests failed!")
        return 1


if __name__ == "__main__":
    sys.exit(main())
