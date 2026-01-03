"""
Adaptive fixing engine module for in-place error correction.

Diagnoses failures, generates fixes, and retries failed steps without
re-running successful ones.
"""

import logging
from typing import Optional, Tuple

from jarvis.execution_models import CodeStep, FailureDiagnosis, ExecutionResult
from jarvis.llm_client import LLMClient

logger = logging.getLogger(__name__)


class AdaptiveFixEngine:
    """
    Diagnoses and fixes failures during code execution.

    When a step fails:
    1. Captures the exact error
    2. Diagnoses root cause
    3. Generates a fix
    4. Re-executes ONLY that step
    5. Continues to next step
    """

    def __init__(self, llm_client: LLMClient) -> None:
        """
        Initialize adaptive fix engine.

        Args:
            llm_client: LLM client for diagnosis and fix generation
        """
        self.llm_client = llm_client
        logger.info("AdaptiveFixEngine initialized")

    def diagnose_failure(
        self,
        step: CodeStep,
        error_type: str,
        error_details: str,
        original_output: str,
    ) -> FailureDiagnosis:
        """
        Use LLM to understand failure and suggest fix.

        Args:
            step: The failed CodeStep
            error_type: Type of error (e.g., ImportError, SyntaxError)
            error_details: Detailed error message
            original_output: Full output from failed execution

        Returns:
            FailureDiagnosis with root cause and suggested fix
        """
        logger.info(f"Diagnosing failure for step {step.step_number}: {error_type}")

        prompt = self._build_diagnosis_prompt(step, error_type, error_details, original_output)

        try:
            response = self.llm_client.generate(prompt)
            logger.debug(f"Diagnosis response received: {len(response)} characters")

            # Parse response into FailureDiagnosis
            diagnosis = self._parse_diagnosis_response(response, error_type, error_details)
            logger.info(f"Diagnosis complete: {diagnosis.root_cause}")
            return diagnosis
        except Exception as e:
            logger.error(f"Failed to diagnose failure: {e}")
            # Return fallback diagnosis
            return FailureDiagnosis(
                error_type=error_type,
                error_details=error_details,
                root_cause=f"Unable to diagnose: {str(e)}",
                suggested_fix="Manual intervention required",
                fix_strategy="manual",
                confidence=0.3,
            )

    def generate_fix(
        self, step: CodeStep, diagnosis: FailureDiagnosis, retry_count: int
    ) -> str:
        """
        Generate fixed code based on diagnosis.

        Args:
            step: Original CodeStep that failed
            diagnosis: FailureDiagnosis with suggested fix
            retry_count: Current retry attempt number

        Returns:
            Fixed code string
        """
        logger.info(f"Generating fix for step {step.step_number} (attempt {retry_count + 1})")

        prompt = self._build_fix_prompt(step, diagnosis, retry_count)

        try:
            fixed_code = self.llm_client.generate(prompt)
            logger.debug(f"Generated fix length: {len(fixed_code)} characters")
            return fixed_code
        except Exception as e:
            logger.error(f"Failed to generate fix: {e}")
            raise

    def retry_step_with_fix(
        self, step: CodeStep, fixed_code: str, max_retries: int = 3
    ) -> Tuple[bool, str, Optional[str]]:
        """
        Execute fixed code and check if it passes.

        Args:
            step: CodeStep with updated code
            fixed_code: Fixed code to execute
            max_retries: Maximum retry attempts

        Returns:
            Tuple of (success, output, error_if_failed)
        """
        logger.info(f"Retrying step {step.step_number} with fix")

        import subprocess
        import tempfile
        import os

        # Write fixed code to temp file
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".py", delete=False
        ) as f:
            f.write(fixed_code)
            temp_file = f.name

        try:
            # Execute fixed code
            result = subprocess.run(
                ["python", temp_file],
                capture_output=True,
                text=True,
                timeout=step.timeout_seconds,
            )

            output = result.stdout + result.stderr

            if result.returncode == 0:
                logger.info(f"Retry successful for step {step.step_number}")
                return True, output, None
            else:
                logger.warning(f"Retry failed for step {step.step_number}: {output[:200]}")
                return False, output, output

        except subprocess.TimeoutExpired:
            error_msg = f"Retry timed out after {step.timeout_seconds} seconds"
            logger.error(error_msg)
            return False, "", error_msg
        except Exception as e:
            error_msg = f"Retry failed with exception: {str(e)}"
            logger.error(error_msg)
            return False, "", error_msg
        finally:
            # Clean up temp file
            try:
                os.unlink(temp_file)
            except Exception:
                pass

    def _build_diagnosis_prompt(
        self,
        step: CodeStep,
        error_type: str,
        error_details: str,
        original_output: str,
    ) -> str:
        """Build prompt for failure diagnosis."""
        prompt = f"""Analyze this code execution failure and provide a detailed diagnosis.

Step Description: {step.description}

Original Code:
```python
{step.code or "No code provided"}
```

Error Type: {error_type}

Error Details:
{error_details}

Full Output:
{original_output[:1000]}

Provide your diagnosis in this JSON format:
{{
  "root_cause": "Clear explanation of what went wrong",
  "suggested_fix": "Specific fix to apply",
  "fix_strategy": "one of: regenerate_code, add_retry_logic, install_package, adjust_parameters, or manual",
  "confidence": 0.0 to 1.0
}}

Common fix strategies:
- regenerate_code: Rewrite the code to fix bugs
- add_retry_logic: Add retry logic with backoff
- install_package: Install missing dependencies
- adjust_parameters: Change parameters or configuration
- manual: Requires human intervention

Return only valid JSON, no other text."""
        return prompt

    def _build_fix_prompt(
        self, step: CodeStep, diagnosis: FailureDiagnosis, retry_count: int
    ) -> str:
        """Build prompt for generating fixed code."""
        prompt = f"""Generate fixed code for this failed step.

Step Description: {step.description}

Original Code:
```python
{step.code or "No code provided"}
```

Diagnosis:
- Root Cause: {diagnosis.root_cause}
- Suggested Fix: {diagnosis.suggested_fix}
- Fix Strategy: {diagnosis.fix_strategy}

This is retry attempt {retry_count + 1}.

Requirements:
1. Fix the issue identified in the diagnosis
2. Follow the suggested fix strategy
3. Add better error handling
4. Make the code more robust
5. Return only the code, no explanations or markdown formatting
6. Ensure the code is complete and executable

Return only the fixed code, no other text."""
        return prompt

    def _parse_diagnosis_response(
        self, response: str, error_type: str, error_details: str
    ) -> FailureDiagnosis:
        """Parse LLM response into FailureDiagnosis."""
        import json
        import re

        try:
            # Try to extract JSON from response
            json_text = self._extract_json_from_response(response)
            data = json.loads(json_text)

            return FailureDiagnosis(
                error_type=error_type,
                error_details=error_details,
                root_cause=data.get("root_cause", "Unknown"),
                suggested_fix=data.get("suggested_fix", "No suggestion"),
                fix_strategy=data.get("fix_strategy", "manual"),
                confidence=float(data.get("confidence", 0.5)),
            )
        except (json.JSONDecodeError, ValueError) as e:
            logger.warning(f"Failed to parse diagnosis response: {e}")
            # Return fallback diagnosis
            return FailureDiagnosis(
                error_type=error_type,
                error_details=error_details,
                root_cause="Failed to parse diagnosis",
                suggested_fix=response[:200],
                fix_strategy="manual",
                confidence=0.4,
            )

    def _extract_json_from_response(self, response: str) -> str:
        """Extract JSON from LLM response."""
        text = response.strip()

        # Try to find JSON in markdown code blocks
        if "```" in text:
            start_idx = text.find("```json")
            if start_idx >= 0:
                start_idx = text.find("\n", start_idx) + 1
                end_idx = text.find("```", start_idx)
                if end_idx > start_idx:
                    return text[start_idx:end_idx].strip()

            # Try generic code block
            start_idx = text.find("```")
            if start_idx >= 0:
                start_idx = text.find("\n", start_idx) + 1
                end_idx = text.find("```", start_idx)
                if end_idx > start_idx:
                    return text[start_idx:end_idx].strip()

        # Try to find JSON object
        json_start = text.find("{")
        json_end = text.rfind("}")
        if json_start >= 0 and json_end > json_start:
            return text[json_start : json_end + 1]

        raise ValueError("No valid JSON found in response")
