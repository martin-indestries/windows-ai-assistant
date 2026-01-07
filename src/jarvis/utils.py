"""
Utility functions for Jarvis.
"""

import ast
import logging
import re
from typing import List, Optional, Tuple

logger = logging.getLogger(__name__)


# Enhanced code cleaning function that uses CodeCleaner class
def clean_code(code: str, raise_on_empty: bool = True) -> str:
    """
    Strip markdown code formatting from generated code.

    Removes markdown backticks (```) and language specifiers from code,
    returning only the raw executable code.

    Args:
        code: Code string that may contain markdown formatting
        raise_on_empty: Whether to raise ValueError if code is empty

    Returns:
        Cleaned code string without markdown formatting

    Raises:
        ValueError: If code is empty and raise_on_empty is True
    """
    if not code:
        if raise_on_empty:
            raise ValueError("Generated code is empty!")
        return ""

    text = code.strip()

    # Remove markdown code blocks with language specifiers
    # Pattern 1: ```python\n...\n```
    # Pattern 2: ```\n...\n```
    # Pattern 3: ```python ... ```

    # Match code blocks with language specifier
    code_block_pattern = r"```(?:\w+)?\s*\n([\s\S]*?)```"
    match = re.search(code_block_pattern, text)

    if match:
        logger.debug("Extracted code from markdown code block")
        return match.group(1).strip()

    # If no code block found, try to remove standalone ``` markers
    # This handles cases like ```code```
    text = re.sub(r"^```\w*\s*", "", text)  # Remove opening ```
    text = re.sub(r"\s*```$", "", text)  # Remove closing ```

    # Clean up any remaining whitespace
    cleaned = text.strip()

    # Detect empty code
    if not cleaned or cleaned.isspace():
        if raise_on_empty:
            raise ValueError("Generated code is empty!")
        return ""

    return cleaned


def truncate_text(text: str, max_length: int, suffix: str = "...") -> str:
    """
    Truncate text to a maximum length.

    Args:
        text: Text to truncate
        max_length: Maximum length of truncated text
        suffix: Suffix to add if text is truncated

    Returns:
        Truncated text
    """
    if len(text) <= max_length:
        return text
    return text[: max_length - len(suffix)] + suffix


def extract_input_calls(code: str) -> List[ast.Call]:
    """
    Extract all input() calls from code using AST parsing.

    Args:
        code: Python source code

    Returns:
        List of input Call nodes with their line numbers
    """
    input_calls = []

    try:
        tree = ast.parse(code)
    except SyntaxError:
        return input_calls

    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            func_name = None
            if isinstance(node.func, ast.Name):
                func_name = node.func.id
            elif isinstance(node.func, ast.Attribute):
                func_name = node.func.attr

            if func_name == "input":
                input_calls.append(node)

    return input_calls


def detect_input_calls(code: str) -> Tuple[int, List[str]]:
    """
    Detect input() calls in code and extract their prompts.

    Args:
        code: Python source code

    Returns:
        Tuple of (count of input calls, list of prompts)
    """
    try:
        tree = ast.parse(code)
    except SyntaxError:
        return 0, []

    input_count = 0
    prompts = []

    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            func_name = None
            if isinstance(node.func, ast.Name):
                func_name = node.func.id
            elif isinstance(node.func, ast.Attribute):
                func_name = node.func.attr

            if func_name == "input":
                input_count += 1
                # Extract prompt if present
                prompt = ""
                if node.args and isinstance(node.args[0], ast.Constant):
                    prompt = node.args[0].value
                elif node.args and isinstance(node.args[0], ast.Str):  # Python 3.7/3.8
                    prompt = node.args[0].s
                prompts.append(prompt)

    return input_count, prompts


def generate_test_inputs(prompts: List[str]) -> List[str]:
    """
    Generate test inputs based on prompt context.

    Args:
        prompts: List of prompt strings from input() calls

    Returns:
        List of test input values
    """
    test_inputs = []

    for i, prompt in enumerate(prompts):
        prompt_lower = prompt.lower()

        # Pattern matching for common input types
        if any(name in prompt_lower for name in ["name", "user", "username", "who"]):
            test_inputs.append("TestUser")
        elif any(word in prompt_lower for word in ["age", "years", "old"]):
            test_inputs.append("25")
        elif any(word in prompt_lower for word in ["number", "num", "count", "quantity"]):
            test_inputs.append("42")
        elif any(word in prompt_lower for word in ["email", "address"]):
            test_inputs.append("test@example.com")
        elif any(word in prompt_lower for word in ["phone", "tel"]):
            test_inputs.append("555-1234")
        elif any(word in prompt_lower for word in ["city", "location", "where"]):
            test_inputs.append("New York")
        elif any(word in prompt_lower for word in ["country", "nation"]):
            test_inputs.append("USA")
        elif any(word in prompt_lower for word in ["date", "when"]):
            test_inputs.append("2024-01-15")
        elif any(word in prompt_lower for word in ["price", "cost", "amount"]):
            test_inputs.append("99.99")
        elif any(word in prompt_lower for word in ["yes", "confirm", "ok"]):
            test_inputs.append("y")
        elif any(word in prompt_lower for word in ["no", "cancel"]):
            test_inputs.append("n")
        elif any(word in prompt_lower for word in ["choice", "select", "option"]):
            test_inputs.append("1")
        elif any(word in prompt_lower for word in ["color", "colour"]):
            test_inputs.append("blue")
        elif any(word in prompt_lower for word in ["food", "eat"]):
            test_inputs.append("pizza")
        elif any(word in prompt_lower for word in ["animal", "pet"]):
            test_inputs.append("dog")
        elif any(word in prompt_lower for word in ["movie", "film"]):
            test_inputs.append("action")
        elif any(word in prompt_lower for word in ["music", "song"]):
            test_inputs.append("rock")
        elif any(word in prompt_lower for word in ["sport", "game"]):
            test_inputs.append("football")
        elif any(word in prompt_lower for word in ["hobby", "interest"]):
            test_inputs.append("reading")
        else:
            # Generic test input based on position
            ordinal = ["first", "second", "third", "fourth", "fifth"][min(i, 4)]
            test_inputs.append(f"test_{ordinal}_value")

    return test_inputs


def has_input_calls(code: str) -> bool:
    """
    Check if code contains any input() calls.

    Args:
        code: Python source code

    Returns:
        True if code contains input() calls
    """
    try:
        tree = ast.parse(code)
    except SyntaxError:
        return False

    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            func_name = None
            if isinstance(node.func, ast.Name):
                func_name = node.func.id
            elif isinstance(node.func, ast.Attribute):
                func_name = node.func.attr

            if func_name == "input":
                return True

    return False
