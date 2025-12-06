# Reasoning Module

## Overview

The Reasoning Module (`jarvis.reasoning`) provides a sophisticated planning and task decomposition engine for the Jarvis AI Assistant. It breaks down user requests into structured, executable plans with built-in validation and safety checks.

## Key Components

### Plan Schema

The module defines a comprehensive plan schema with the following hierarchy:

- **Plan**: Top-level container for an execution plan
  - `plan_id`: Unique identifier for the plan
  - `user_input`: Original user request
  - `description`: High-level summary of the plan
  - `steps`: List of PlanStep objects
  - `validation_result`: Results of validation checks
  - `is_safe`: Safety verification flag
  - `generated_at`: Timestamp of generation
  - `verified_at`: Timestamp of verification

- **PlanStep**: Individual action in the plan
  - `step_number`: Sequential step number
  - `description`: Action description
  - `required_tools`: List of tools needed
  - `dependencies`: List of prerequisite step numbers
  - `safety_flags`: Safety concerns (destructive, network_access, file_modification, system_command, external_dependency)
  - `estimated_duration`: Time estimate
  - `status`: Current execution status (pending, in_progress, completed, failed, skipped)
  - `validation_notes`: Validation feedback

- **PlanValidationResult**: Validation check results
  - `is_valid`: Whether the plan is logically valid
  - `issues`: Critical errors found
  - `warnings`: Non-critical warnings
  - `safety_concerns`: Identified safety issues

### ReasoningModule

The main reasoning engine with the following interface:

```python
from jarvis.reasoning import ReasoningModule
from jarvis.config import JarvisConfig
from jarvis.llm_client import LLMClient

config = JarvisConfig()
llm_client = LLMClient(config.llm)
reasoning = ReasoningModule(config=config, llm_client=llm_client)

# Generate and verify a plan
plan = reasoning.plan_actions("Migrate database to new schema")
```

## Workflow

### 1. Plan Generation

When `plan_actions()` is called:

1. Validates user input is not empty
2. Builds a structured prompt for the LLM
3. Calls the LLM client to generate steps
4. Parses the LLM response into PlanStep objects
5. Falls back to a basic 3-step plan if parsing fails

### 2. Self-Verification Pass

The plan is automatically verified for:

**Dependency Checks:**
- No missing dependencies
- No forward/circular references
- All step numbers are sequential

**Sequence Checks:**
- Steps are properly numbered 1, 2, 3, ...
- No gaps in the sequence

**Logical Consistency:**
- First step has no dependencies
- Each step has a meaningful description
- Warnings for potential issues

**Safety Checks:**
- Identifies destructive operations
- Flags system command execution
- Detects file modifications
- Warns about external dependencies

### 3. Plan Validation Result

The validation process produces:
- `is_valid`: True if no critical issues found
- `issues`: List of errors that prevent execution
- `warnings`: Non-blocking concerns
- `safety_concerns`: Operations requiring approval

## Safety Flags

Available safety flags indicate operation characteristics:

- `DESTRUCTIVE`: Operation permanently removes/modifies data
- `NETWORK_ACCESS`: Operation requires network connectivity
- `FILE_MODIFICATION`: Operation reads/writes files
- `SYSTEM_COMMAND`: Operation executes system-level commands
- `EXTERNAL_DEPENDENCY`: Operation requires external tools/services

## Integration with Container

The ReasoningModule is registered in the DI container:

```python
from jarvis.container import Container

container = Container()
reasoning_module = container.get_reasoning_module()
plan = reasoning_module.plan_actions("your task here")
```

## LLM Mocking for Testing

The module works seamlessly with mocked LLM clients for testing:

```python
from unittest.mock import MagicMock
from jarvis.reasoning import ReasoningModule

llm_client = MagicMock()
llm_client.extract_tool_knowledge.return_value = {
    "description": "Test plan",
    "steps": [
        {
            "step_number": 1,
            "description": "First step",
            "required_tools": ["tool1"],
            "dependencies": [],
            "safety_flags": [],
        }
    ]
}

reasoning = ReasoningModule(config=config, llm_client=llm_client)
plan = reasoning.plan_actions("test input")
```

## Deterministic Prompts

The planning prompt is fully configurable via `_build_planning_prompt()`:

```python
prompt = reasoning_module._build_planning_prompt("user request")
# Prompt includes:
# - Clear instructions for step breakdown
# - Expected JSON structure
# - Validation requirements
# - Safety flag definitions
```

## Examples

### Simple Linear Plan

```python
plan = reasoning.plan_actions("Create a backup of my database")
# Generates:
# 1. Stop write operations
# 2. Create backup
# 3. Verify backup integrity
# 4. Resume operations
```

### Complex Plan with Dependencies

```python
plan = reasoning.plan_actions("Deploy new version with zero downtime")
# Generates:
# 1. Prepare new infrastructure (parallel with step 2)
# 2. Prepare rollback plan
# 3. Deploy to canary (depends on 1, 2)
# 4. Run tests (depends on 3)
# 5. Gradual rollout (depends on 4)
# 6. Monitor (depends on 5)
# 7. Cleanup old resources (depends on 6)
```

## Testing

The module includes comprehensive test coverage:

- 40 unit tests covering all major functionality
- 93% code coverage
- Tests for plan structuring, validation, and safety checks
- Mock-based testing without requiring actual LLM

Run tests:

```bash
python -m pytest tests/test_reasoning.py -v
```

## Best Practices

1. **Always check validation results**: Use `plan.is_valid_and_safe()` before execution
2. **Review safety concerns**: Plans with destructive operations should require approval
3. **Handle fallback plans**: The module generates 3-step fallback plans on parsing failure
4. **Monitor generation**: Check log messages for warnings about plan quality
5. **Cache plans**: Reuse validated plans for identical user inputs

## Configuration

Safety validation is controlled by configuration:

```python
config = JarvisConfig()
config.safety.enable_input_validation = True  # Enable safety checks
config.llm.temperature = 0.3  # Lower temperature for more deterministic plans
```

## Future Enhancements

- Parallel step execution support
- Interactive plan refinement
- Cost estimation for cloud resources
- Historical plan tracking and optimization
- Integration with orchestrator for automatic execution
