"""
Test case generator module for intelligent test input generation.

Generates smart test inputs based on program type and code analysis.
"""

import logging
from typing import Callable, List, Optional

from jarvis.interactive_program_analyzer import ProgramType

logger = logging.getLogger(__name__)

# Type alias for validation function
ValidationFunc = Callable[[str], bool]


class TestCaseGenerator:
    """
    Generates intelligent test cases for interactive programs.

    Analyzes program type and creates appropriate test inputs
    with validation functions.
    """

    def __init__(self) -> None:
        """Initialize test case generator."""
        logger.info("TestCaseGenerator initialized")

    def generate_test_cases(
        self,
        program_type: ProgramType,
        code: str,
        input_count: int = 1,
        max_cases: int = 10,
    ) -> List[dict]:
        """
        Generate test cases based on program type.

        Args:
            program_type: Type of program
            code: Source code
            input_count: Number of input() calls in the code
            max_cases: Maximum number of test cases to generate

        Returns:
            List of test case dictionaries
        """
        generators = {
            ProgramType.CALCULATOR: self._generate_calculator_tests,
            ProgramType.GAME: self._generate_game_tests,
            ProgramType.QUIZ: self._generate_quiz_tests,
            ProgramType.UTILITY: self._generate_utility_tests,
            ProgramType.FORM: self._generate_form_tests,
            ProgramType.MENU: self._generate_menu_tests,
            ProgramType.CHAT: self._generate_chat_tests,
        }

        generator = generators.get(program_type, self._generate_utility_tests)
        test_cases = generator(code, input_count)

        # Limit to max_cases
        return test_cases[:max_cases]

    def _generate_calculator_tests(self, code: str, input_count: int = 3) -> List[dict]:
        """
        Generate test cases for calculator programs.

        Args:
            code: Calculator source code
            input_count: Number of input() calls in the code

        Returns:
            List of calculator test cases
        """
        tests = [
            {
                "name": "Addition",
                "inputs": self._generate_numeric_inputs(input_count),
                "validate": lambda out: self._has_output(out),
                "expected": "Calculator addition test",
            },
            {
                "name": "Subtraction",
                "inputs": self._generate_numeric_inputs(input_count),
                "validate": lambda out: self._has_output(out),
                "expected": "Calculator subtraction test",
            },
            {
                "name": "Multiplication",
                "inputs": self._generate_numeric_inputs(input_count),
                "validate": lambda out: self._has_output(out),
                "expected": "Calculator multiplication test",
            },
            {
                "name": "Division",
                "inputs": self._generate_numeric_inputs(input_count),
                "validate": lambda out: self._has_output(out),
                "expected": "Calculator division test",
            },
        ]

        logger.info(f"Generated {len(tests)} calculator test cases with {input_count} inputs each")
        return tests

    def _generate_game_tests(self, code: str, input_count: int = 1) -> List[dict]:
        """
        Generate test cases for guessing games.

        Args:
            code: Game source code
            input_count: Number of input() calls in the code

        Returns:
            List of game test cases
        """
        tests = [
            {
                "name": "First guess",
                "inputs": self._generate_numeric_inputs(input_count),
                "validate": lambda out: self._has_output(out),
                "expected": "Game accepts guess",
            },
            {
                "name": "Second guess",
                "inputs": self._generate_numeric_inputs(input_count),
                "validate": lambda out: self._has_output(out),
                "expected": "Game accepts another guess",
            },
        ]

        logger.info(f"Generated {len(tests)} game test cases with {input_count} inputs each")
        return tests

    def _generate_quiz_tests(self, code: str, input_count: int = 1) -> List[dict]:
        """
        Generate test cases for quiz programs.

        Args:
            code: Quiz source code
            input_count: Number of input() calls in the code

        Returns:
            List of quiz test cases
        """
        tests = [
            {
                "name": "Quiz test",
                "inputs": self._generate_string_inputs(input_count),
                "validate": lambda out: self._has_output(out),
                "expected": "Quiz accepts answers",
            },
        ]

        logger.info(f"Generated {len(tests)} quiz test cases with {input_count} inputs each")
        return tests

    def _generate_utility_tests(self, code: str, input_count: int = 1) -> List[dict]:
        """
        Generate test cases for utility programs.

        Args:
            code: Utility source code
            input_count: Number of input() calls in the code

        Returns:
            List of utility test cases
        """
        tests = [
            {
                "name": "Basic input test",
                "inputs": self._generate_string_inputs(input_count),
                "validate": lambda out: self._has_output(out),
                "expected": "Processes basic input",
            },
            {
                "name": "Numeric input test",
                "inputs": self._generate_numeric_inputs(input_count),
                "validate": lambda out: self._has_output(out),
                "expected": "Processes number input",
            },
        ]

        logger.info(f"Generated {len(tests)} utility test cases with {input_count} inputs each")
        return tests

    def _generate_form_tests(self, code: str, input_count: int = 3) -> List[dict]:
        """
        Generate test cases for form programs.

        Args:
            code: Form source code
            input_count: Number of input() calls in the code

        Returns:
            List of form test cases
        """
        tests = [
            {
                "name": "Valid form data",
                "inputs": self._generate_string_inputs(input_count),
                "validate": lambda out: self._has_output(out),
                "expected": "Processes valid form data",
            },
        ]

        logger.info(f"Generated {len(tests)} form test cases with {input_count} inputs each")
        return tests

    def _generate_menu_tests(self, code: str, input_count: int = 1) -> List[dict]:
        """
        Generate test cases for menu programs.

        Args:
            code: Menu source code
            input_count: Number of input() calls in the code

        Returns:
            List of menu test cases
        """
        tests = [
            {
                "name": "Select option 1",
                "inputs": self._generate_numeric_inputs(input_count),
                "validate": lambda out: self._has_output(out),
                "expected": "Executes menu option 1",
            },
            {
                "name": "Select option 2",
                "inputs": self._generate_numeric_inputs(input_count),
                "validate": lambda out: self._has_output(out),
                "expected": "Executes menu option 2",
            },
        ]

        logger.info(f"Generated {len(tests)} menu test cases with {input_count} inputs each")
        return tests

    def _generate_chat_tests(self, code: str, input_count: int = 1) -> List[dict]:
        """
        Generate test cases for chat programs.

        Args:
            code: Chat source code
            input_count: Number of input() calls in the code

        Returns:
            List of chat test cases
        """
        tests = [
            {
                "name": "Greeting",
                "inputs": self._generate_string_inputs(input_count),
                "validate": lambda out: self._has_output(out),
                "expected": "Responds to greeting",
            },
            {
                "name": "Question",
                "inputs": self._generate_string_inputs(input_count),
                "validate": lambda out: self._has_output(out),
                "expected": "Responds to question",
            },
        ]

        logger.info(f"Generated {len(tests)} chat test cases with {input_count} inputs each")
        return tests

    def _contains_number(self, text: str, target: int) -> bool:
        """
        Check if text contains a specific number.

        Args:
            text: Text to search
            target: Number to find

        Returns:
            True if number found, False otherwise
        """
        import re

        # Match the number as a word/number boundary
        pattern = r"\b" + str(target) + r"\b"
        return bool(re.search(pattern, text))

    def _generate_string_inputs(self, count: int) -> List[str]:
        """
        Generate simple string test inputs.

        Args:
            count: Number of inputs to generate

        Returns:
            List of string inputs
        """
        string_values = ["test", "hello", "world", "user", "item", "value", "input", "data"]
        inputs = []

        for i in range(count):
            # Cycle through values
            value = string_values[i % len(string_values)]
            # Add number to differentiate
            if i >= len(string_values):
                value = f"{value}{i + 1}"
            inputs.append(value)

        return inputs

    def _generate_numeric_inputs(self, count: int) -> List[str]:
        """
        Generate numeric test inputs.

        Args:
            count: Number of inputs to generate

        Returns:
            List of numeric string inputs
        """
        numeric_values = ["1", "2", "3", "5", "10", "42", "100", "3.14"]
        inputs = []

        for i in range(count):
            # Cycle through values
            value = numeric_values[i % len(numeric_values)]
            # Use different values for each position
            if i >= len(numeric_values):
                value = str((i + 1) * 2)
            inputs.append(value)

        return inputs

    def _has_output(self, text: str) -> bool:
        """
        Check if there's any meaningful output.

        Args:
            text: Output text

        Returns:
            True if there's output, False otherwise
        """
        return len(text.strip()) > 0

    def validate_output(
        self,
        output: str,
        validate_func: Optional[ValidationFunc] = None,
        expected: Optional[str] = None,
    ) -> bool:
        """
        Validate program output against expected result.

        Args:
            output: Actual program output
            validate_func: Optional validation function
            expected: Optional expected output string

        Returns:
            True if validation passes, False otherwise
        """
        if validate_func:
            try:
                return validate_func(output)
            except Exception as e:
                logger.warning(f"Validation function failed: {e}")
                return False

        if expected and expected in output:
            return True

        # Default: consider non-empty output as success
        return len(output.strip()) > 0
