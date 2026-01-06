"""
Prompt injector module for automatically adding visible prompts to input() calls.

This module analyzes Python code using AST parsing to find all input() calls
and adds meaningful prompts to make test inputs flow automatically.
"""

import ast
import logging
import re
from typing import List, Optional

logger = logging.getLogger(__name__)


class PromptInjector:
    """
    Automatically adds visible prompts to input() calls.

    Features:
    - Uses AST parsing to find all input() calls
    - Adds context-aware prompts (first, second, third, etc.)
    - Preserves existing prompts
    - Handles edge cases (loops, conditionals, function calls)
    """

    # Ordinal words for sequential inputs
    ORDINAL_WORDS = [
        "first",
        "second",
        "third",
        "fourth",
        "fifth",
        "sixth",
        "seventh",
        "eighth",
        "ninth",
        "tenth",
    ]

    # Generic prompts for different contexts
    GENERIC_PROMPTS = [
        "Enter value: ",
        "Enter input: ",
        "Please enter a value: ",
        "Enter: ",
    ]

    def __init__(self, debug_enabled: bool = False) -> None:
        """
        Initialize prompt injector.

        Args:
            debug_enabled: Enable debug logging
        """
        self.debug_enabled = debug_enabled
        logger.info("PromptInjector initialized")

    def inject_prompts(self, code: str, log_id: Optional[str] = None) -> str:
        """
        Analyze code for input() calls and add meaningful prompts.

        BEFORE:
        num1 = input()
        num2 = input()
        result = num1 + num2

        AFTER:
        num1 = input("Enter first number: ")
        num2 = input("Enter second number: ")
        result = num1 + num2

        Args:
            code: Python source code
            log_id: Optional identifier for logging

        Returns:
            Code with prompts injected
        """
        if not code or not code.strip():
            return code

        # Parse code into AST
        try:
            tree = ast.parse(code)
        except SyntaxError as e:
            logger.warning(f"Failed to parse code for prompt injection: {e}")
            return code

        # Find all input() calls that need prompts
        inputs_needing_prompts = self._find_input_calls(tree)

        if not inputs_needing_prompts:
            logger.debug("No input() calls found requiring prompts")
            return code

        logger.info(f"Found {len(inputs_needing_prompts)} input() calls needing prompts")

        # Generate prompts for each input
        prompts = self._generate_prompts(inputs_needing_prompts, code)

        # Apply prompts to source code
        modified_code = self._apply_prompts(code, inputs_needing_prompts, prompts)

        if log_id and self.debug_enabled:
            self._log_injection(log_id, len(inputs_needing_prompts), modified_code)

        return modified_code

    def _find_input_calls(self, tree: ast.AST) -> List[ast.Call]:
        """
        Find all input() calls that don't already have a string argument.

        Args:
            tree: Parsed AST tree

        Returns:
            List of input Call nodes needing prompts
        """
        inputs_needing_prompts = []

        for node in ast.walk(tree):
            if isinstance(node, ast.Call):
                # Check if it's a call to input()
                func_name = None
                if isinstance(node.func, ast.Name):
                    func_name = node.func.id
                elif isinstance(node.func, ast.Attribute):
                    func_name = node.func.attr

                if func_name == "input":
                    # Check if it already has a string argument
                    has_string_arg = False
                    for arg in node.args:
                        if isinstance(arg, ast.Constant) and isinstance(arg.value, str):
                            has_string_arg = True
                            break
                        if isinstance(arg, ast.Str):  # Python 3.7/3.8 compatibility
                            has_string_arg = True
                            break

                    if not has_string_arg:
                        inputs_needing_prompts.append(node)

        return inputs_needing_prompts

    def _generate_prompts(self, input_calls: List[ast.Call], code: str) -> List[str]:
        """
        Generate appropriate prompts for each input call.

        Args:
            input_calls: List of input Call nodes
            code: Original source code

        Returns:
            List of prompt strings
        """
        prompts = []
        ordinal_index = 0

        # Get line numbers to understand context
        input_lines = {}
        for call in input_calls:
            if hasattr(call, "lineno"):
                input_lines[call.lineno] = call

        # Sort by line number
        sorted_lines = sorted(input_lines.keys())

        for i, line_no in enumerate(sorted_lines):
            call = input_lines[line_no]

            # Generate ordinal-based prompt
            if ordinal_index < len(self.ORDINAL_WORDS):
                ordinal = self.ORDINAL_WORDS[ordinal_index]
            else:
                ordinal = f"#{ordinal_index + 1}"

            # Try to infer context from surrounding code
            context_prompt = self._infer_context(i, code, line_no)

            if context_prompt:
                prompt = f"Enter {ordinal} {context_prompt}: "
            else:
                prompt = f"Enter {ordinal} value: "

            prompts.append(prompt)
            ordinal_index += 1

        return prompts

    def _infer_context(self, input_index: int, code: str, line_no: int) -> Optional[str]:
        """
        Try to infer the context of an input call from surrounding code.

        Args:
            input_index: Index of this input in sequence
            code: Source code
            line_no: Line number of the input call

        Returns:
            Context string or None if unable to determine
        """
        lines = code.split("\n")

        if line_no > len(lines):
            return None

        # Look at the line before for variable name hints
        if line_no > 1:
            prev_line = lines[line_no - 2].strip()  # -2 because lines are 0-indexed

            # Check for variable assignment patterns like "num1 = input()"
            import re

            # Try to extract variable name
            var_pattern = r"^(\w+)\s*=\s*"
            match = re.match(var_pattern, prev_line)
            if match:
                var_name = match.group(1)
                # Try to make it human-readable
                return self._make_readable(var_name)

        # Look at comments near the input
        for offset in range(1, 4):  # Check up to 3 lines before
            check_line = line_no - offset - 1
            if check_line >= 0 and check_line < len(lines):
                line = lines[check_line].strip()
                if line.startswith("#"):
                    # Extract comment text and make it readable
                    comment = line.lstrip("#").strip()
                    return self._make_readable(comment)

        return None

    def _make_readable(self, text: str) -> str:
        """
        Convert variable name or text to a readable prompt.

        Args:
            text: Variable name or text

        Returns:
            Human-readable string
        """
        # Convert snake_case to words
        text = text.replace("_", " ")

        # Remove common prefixes/suffixes
        text = re.sub(r"^(val|num|input|entry|user_)\s*", "", text, flags=re.IGNORECASE)
        text = re.sub(r"\s*(val|num|input|entry)$", "", text, flags=re.IGNORECASE)

        # Clean up whitespace
        text = " ".join(text.split())

        return text if text else ""

    def _apply_prompts(self, code: str, input_calls: List[ast.Call], prompts: List[str]) -> str:
        """
        Apply generated prompts to the source code.

        Args:
            code: Original source code
            input_calls: List of input Call nodes
            prompts: List of prompt strings

        Returns:
            Modified source code with prompts
        """
        if not input_calls or not prompts:
            return code

        lines = code.split("\n")
        modified_lines = []

        # Create a mapping of line numbers to prompts
        prompt_map = {}
        for call, prompt in zip(input_calls, prompts):
            if hasattr(call, "lineno"):
                prompt_map[call.lineno] = prompt

        for i, line in enumerate(lines, 1):
            if i in prompt_map:
                # This line contains an input() needing a prompt
                modified_line = self._inject_prompt_into_line(line, prompt_map[i])
                modified_lines.append(modified_line)
            else:
                modified_lines.append(line)

        return "\n".join(modified_lines)

    def _inject_prompt_into_line(self, line: str, prompt: str) -> str:
        """
        Inject a prompt into a line containing input().

        Args:
            line: Source line
            prompt: Prompt string to inject

        Returns:
            Modified line with prompt
        """
        import re

        # Find input() and add the prompt
        # Pattern: input() or input(  ) or input(  arg  )
        pattern = r"(\s*input\s*\(\s*)(\))"

        def replacer(match):
            return f'{match.group(1)}"{prompt}"{match.group(2)}'

        modified = re.sub(pattern, replacer, line)

        return modified

    def count_input_calls(self, code: str) -> int:
        """
        Count the number of input() calls in code.

        Args:
            code: Python source code

        Returns:
            Number of input() calls
        """
        try:
            tree = ast.parse(code)
        except SyntaxError:
            return 0

        count = 0
        for node in ast.walk(tree):
            if isinstance(node, ast.Call):
                func_name = None
                if isinstance(node.func, ast.Name):
                    func_name = node.func.id
                elif isinstance(node.func, ast.Attribute):
                    func_name = node.func.attr

                if func_name == "input":
                    count += 1

        return count

    def has_existing_prompts(self, code: str) -> bool:
        """
        Check if code already has prompts in input() calls.

        Args:
            code: Python source code

        Returns:
            True if any input() has a string argument
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
                    for arg in node.args:
                        if isinstance(arg, ast.Constant) and isinstance(arg.value, str):
                            return True
                        if isinstance(arg, ast.Str):
                            return True

        return False

    def _log_injection(self, log_id: str, count: int, modified_code: str) -> None:
        """
        Log prompt injection details.

        Args:
            log_id: Log identifier
            count: Number of prompts injected
            modified_code: Modified code
        """
        logger.info(
            f"Prompt injection for {log_id}: {count} prompts injected, "
            f"code length: {len(modified_code)}"
        )
