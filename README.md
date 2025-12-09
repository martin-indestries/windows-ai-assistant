# Jarvis - Advanced Windows AI Assistant

A Python-based AI assistant with local LLM support, offering natural language command processing with configurable safety features and storage management.

## Project Structure

```
jarvis/
├── src/jarvis/                 # Main package
│   ├── __init__.py
│   ├── __main__.py             # Module entry point
│   ├── app.py                  # GUI application (CustomTkinter)
│   ├── cli.py                  # CLI argument parsing and entry point
│   ├── config.py               # Configuration loading and management
│   ├── container.py            # Dependency injection container
│   ├── document_parser.py      # Document parsing (text, PDF)
│   ├── executor/               # Executor LLM for fast execution
│   │   ├── __init__.py
│   │   └── server.py           # ExecutorServer class
│   ├── learn.py                # Learn CLI module
│   ├── learn/
│   │   ├── __init__.py
│   │   └── __main__.py         # Learn subcommand entry point
│   ├── learn_cli.py            # Learn command implementation
│   ├── llm_client.py           # LLM interaction for capability extraction
│   ├── logging_config.py       # Logging setup
│   ├── memory.py               # Tool knowledge memory store
│   ├── orchestrator.py         # Central command orchestration
│   ├── tool_teaching.py        # Tool Teaching Module
│   ├── voice/                  # Voice interface package
│   │   ├── __init__.py
│   │   └── voice_interface.py  # Wake-word detection and STT
│   └── action_executor.py      # Fast action execution layer
├── tests/                      # Test suite
│   ├── __init__.py
│   ├── test_action_executor.py # Action executor tests
│   ├── test_chat.py            # Chat session tests
│   ├── test_cli.py             # CLI tests
│   ├── test_config.py          # Configuration tests
│   ├── test_container.py       # Container tests
│   ├── test_gui.py             # GUI application tests
│   ├── test_gui_cli_integration.py # GUI-CLI integration tests
│   ├── test_learn_cli.py       # Learn CLI tests
│   ├── test_llm_client.py      # LLM client tests
│   ├── test_orchestrator.py    # Orchestrator tests
│   ├── test_tool_teaching.py   # Tool Teaching Module tests
│   ├── test_voice.py           # Voice interface tests
│   └── test_integration.py     # Integration tests
├── examples/                   # Example files
│   └── sample_tool_doc.md      # Sample tool documentation
├── pyproject.toml              # Project metadata and build configuration
├── requirements.txt            # Runtime dependencies
├── requirements-dev.txt        # Development dependencies
├── GUI_MODE.md                 # GUI and voice documentation
├── CHAT_MODE.md                # Chat mode documentation
└── README.md                   # This file
```

## Features

- **LLM Integration**: Local LLM support via Ollama with `llama3` as the default model
  - No API keys required
  - Privacy-focused: all processing happens locally
  - Easy model switching via configuration
  - **Dual-Model Architecture**: Optional separate Brain (reasoning) and Executor (fast execution) models
    - Brain: DeepSeek-R1-Distill-Llama-70B for deep reasoning and planning
    - Executor: LLaMA 3.1 8B/12B for quick command execution
    - Independent hardware optimization for each model

- **Configuration Management**: Load settings from YAML or JSON files with support for:
  - LLM provider configuration (provider, model, URL, temperature, token limits)
  - Safety toggles (input validation, output filtering)
  - Storage paths (data, logs, config)

- **Tool Teaching Module**: Learn tool capabilities from documentation:
  - Ingest documentation from text, markdown, or PDF files
  - Extract structured capability summaries using LLM
  - Store tool knowledge in persistent memory layer
  - Search and retrieve learned tool knowledge for planning
  - CLI command for triggering tool learning

- **GUI Interface**: Modern graphical interface with CustomTkinter:
  - Dark/light theme support
  - Intent classification vs fast actions workflow
  - Real-time response streaming
  - Command history and auto-completion
  - Safety feature visualization
  - Export chat history functionality

- **Action Execution**: Intelligent command execution with safety controls:
  - Intent-based classification for quick recognition
  - File operation allowlist/denylist system
  - Dry-run mode for previewing actions
  - Automatic retry logic for resilience
  - Timeout-based execution limits

- **Interactive Chat Mode**: Continuous conversation interface:
   - ChatGPT-like interactive prompt
   - Conversation history with context
   - Streaming response display
   - Real-time plan and execution feedback

- **Voice Control**: Optional voice interface for hands-free operation:
   - Wake-word detection ("Jarvis" or custom)
   - Automatic speech-to-text conversion
   - State machine for reliable voice processing
   - Visual feedback for voice activity
   - Seamless integration with GUI and chat modes

- **Natural Language CLI**: Accept commands via command line and route them through orchestrator

- **Dependency Injection**: Loosely coupled, independently testable modules via the Container class

- **Logging**: Configured logging with console and file handlers, rotatable log files

- **Type Hints**: Full type annotations for better IDE support and code clarity

- **Comprehensive Tests**: Unit tests with 90%+ coverage for all modules including GUI, actions, and intent classification

## Requirements

- Python 3.9+
- See `requirements.txt` for dependencies

## Installation

### 1. Clone the repository
```bash
git clone <repository-url>
cd jarvis
```

### 2. Create a virtual environment
```bash
python3 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

### 3. Install the package and dependencies

**For development (with all dev tools):**
```bash
pip install -e ".[dev]"
# or
pip install -r requirements-dev.txt
```

**For production:**
```bash
pip install -e .
# or
pip install -r requirements.txt
```

### 4. GUI Prerequisites (Optional)

The GUI mode requires additional dependencies beyond the core package:

**All platforms:**
- CustomTkinter (included in `requirements.txt`)
- requests (included in `requirements.txt`)
- pyautogui (included in `requirements.txt`)

**Linux specific:**
- On Linux, CustomTkinter requires X11 development libraries:
```bash
# Ubuntu/Debian
sudo apt-get install python3-tk

# Fedora
sudo dnf install python3-tkinter

# Arch
sudo pacman -S tk
```

**Verify GUI installation:**
```bash
# Test if GUI dependencies are available
python3 -c "import customtkinter; print('GUI ready!')"
```

Once installed, launch the GUI with:
```bash
python -m jarvis --gui
```

## Configuration

Configuration can be provided via YAML or JSON files. By default, Jarvis uses sensible defaults with `llama3` as the default LLM model.

### Ollama Setup

Jarvis requires Ollama to be running locally with the `llama3` model available. Follow these steps to set up:

1. **Install Ollama**: Download and install from [ollama.ai](https://ollama.ai)

2. **Start Ollama service**:
```bash
ollama serve
```

3. **Pull the default model** (in another terminal):
```bash
ollama pull llama3
```

By default, Ollama runs on `http://localhost:11434`, which is what Jarvis expects.

### Configuration File Locations

Configuration files can be specified via CLI:
```bash
python -m jarvis --config /path/to/config.yaml "your command"
```

### Configuration File Format

**config.yaml:**
```yaml
debug: false

llm:
  provider: ollama
  model: llama3
  base_url: http://localhost:11434
  temperature: 0.7
  max_tokens: 2048
  timeout: 60

safety:
  enable_input_validation: true
  enable_output_filtering: true
  max_command_length: 10000

storage:
  data_dir: ~/.jarvis/data
  logs_dir: ~/.jarvis/logs
  config_file: ~/.jarvis/config.yaml
```

**config.json:**
```json
{
  "debug": false,
  "llm": {
    "provider": "ollama",
    "model": "llama3",
    "base_url": "http://localhost:11434",
    "temperature": 0.7,
    "max_tokens": 2048,
    "timeout": 60
  },
  "safety": {
    "enable_input_validation": true,
    "enable_output_filtering": true,
    "max_command_length": 10000
  },
  "storage": {
    "data_dir": "~/.jarvis/data",
    "logs_dir": "~/.jarvis/logs",
    "config_file": "~/.jarvis/config.yaml"
  }
}
```

### LLM Request Timeout Configuration

The `timeout` parameter controls how long Jarvis will wait for LLM responses. This is important when using large models.

**Recommended timeouts by model:**
- **llama3**: 30-60 seconds (good balance of speed and capability)
- **gpt-oss:20b**: 60-120 seconds (large model, needs time to respond)
- **mistral**: 30-60 seconds (medium model)
- **neural-chat**: 20-40 seconds (smaller model)
- **default**: 60 seconds

If you encounter timeout errors with large models, increase the timeout value:
```yaml
llm:
  model: gpt-oss:20b
  timeout: 120  # Increase to 2 minutes for large models
```

On slower hardware or with very large models, you may need even longer:
```yaml
llm:
  model: gpt-oss:20b
  timeout: 180  # 3 minutes for very large models
```

### Dual-Model Configuration (Advanced)

Jarvis supports a dual-model architecture where separate LLMs handle reasoning/planning (Brain) and execution (Executor). This allows you to use a powerful reasoning model for complex planning while maintaining fast responses with a lighter executor model.

**Key Benefits:**
- **Brain Model**: Deep reasoning and planning with DeepSeek-R1-Distill-Llama-70B Q4_K_M
- **Executor Model**: Fast execution with LLaMA 3.1 8B or 12B
- **Hardware optimization**: Independent configuration of CPU/GPU resources for each model
- **Fallback support**: Automatically falls back to single LLM mode if disabled

**Configuration example:**
```yaml
dual_llm:
  enabled: true  # Enable dual-model mode
  
  # Brain LLM: Deep reasoning and planning
  brain:
    provider: ollama
    model: deepseek-r1:70b-qwen-distill-q4_K_M
    base_url: http://localhost:11434
    temperature: 0.5  # Lower for deterministic reasoning
    max_tokens: 4096  # Larger for detailed plans
    timeout: 120  # Longer timeout (2+ minutes)
    
    # Hardware hints for Ollama
    num_gpu: 1        # GPU layers (0 for CPU-only)
    num_thread: 8     # CPU threads
    num_ctx: 8192     # Context window
    cpu_ram_gb: 64    # Recommended CPU RAM
    gpu_vram_gb: 24   # Recommended GPU VRAM
  
  # Executor LLM: Fast execution
  executor:
    provider: ollama
    model: llama3.1:8b
    base_url: http://localhost:11434
    temperature: 0.7  # Moderate for natural responses
    max_tokens: 2048
    timeout: 30       # Fast timeout
    
    # Hardware hints for Ollama
    num_gpu: 1
    num_thread: 4
    num_ctx: 4096
    cpu_ram_gb: 16
    gpu_vram_gb: 8
```

**Setting up dual models:**

1. **Pull both models from Ollama:**
```bash
ollama pull deepseek-r1:70b-qwen-distill-q4_K_M
ollama pull llama3.1:8b
```

2. **Update your config file** to enable `dual_llm.enabled: true`

3. **Access the models in code:**
```python
from jarvis.container import Container

container = Container()
manager = container.get_dual_model_manager()

# Check if dual mode is active
if manager.is_dual_mode_enabled():
    brain = manager.get_brain_server()
    executor = manager.get_executor_server()
    
    # Use brain for planning
    plan = brain.plan("Complex reasoning task")
    
    # Use executor for fast execution
    result = executor.execute("Quick command")
```

**Hardware recommendations:**
- **Brain (70B model)**: 64GB CPU RAM or 24GB GPU VRAM
- **Executor (8B model)**: 16GB CPU RAM or 8GB GPU VRAM
- Consider using CPU for one model and GPU for the other to balance resources

### Overriding the Model

You can override the default model in several ways:

1. **Via configuration file**: Update the `llm.model` field in your `config.yaml` or `config.json`
2. **Via environment variable**: Set `JARVIS_LLM_MODEL` (future implementation)
3. **Via CLI flag**: Use `--model` when running Jarvis (future implementation)

## Usage

### Tool Teaching - Learning from Documentation

The Tool Teaching Module allows Jarvis to learn new tool capabilities from documentation files.

**Basic usage:**
```bash
python -m jarvis.learn --source /path/to/tool_documentation.txt
```

**With verbose progress output:**
```bash
python -m jarvis.learn --source /path/to/tool_doc.md --verbose
```

**With debug logging:**
```bash
python -m jarvis.learn --source /path/to/tool_doc.pdf --debug
```

**With custom configuration:**
```bash
python -m jarvis.learn --source ./docs/tool.txt --config config.yaml
```

**Supported file formats:**
- Text files (.txt)
- Markdown files (.md)
- PDF files (.pdf)

**Example:**
```bash
# Learn file operations from documentation
python -m jarvis.learn --source examples/sample_tool_doc.md --verbose

# Output:
# [INFO] Learning from: examples/sample_tool_doc.md
# [INFO] Parsing document: examples/sample_tool_doc.md
# [INFO] Document parsed (8234 characters)
# [INFO] Extracting tool knowledge with LLM
# [INFO] Tool knowledge extracted
# [INFO] Storing tool capabilities
# [INFO] Stored tool: file_tool
# [INFO] Learning complete. Learned 1 tools
# 
# Successfully learned 1 tool(s)
#   - file_tool
```

**Accessing learned tool knowledge in code:**
```python
from jarvis.container import Container

container = Container()
tool_teaching = container.get_tool_teaching_module()

# Learn from document
learned_tools = tool_teaching.learn_from_document("docs/tool.txt")

# Retrieve tool knowledge
file_tool_knowledge = tool_teaching.get_tool_knowledge("file_tool")
print(f"Commands: {file_tool_knowledge.commands}")
print(f"Parameters: {file_tool_knowledge.parameters}")

# Search for tools
search_results = tool_teaching.search_tools("file")
print(f"Found tools: {search_results}")

# Use learned knowledge in orchestrator
orchestrator = container.get_orchestrator()
file_tool = orchestrator.get_tool_knowledge("file_tool")
all_tools = orchestrator.list_available_tools()
```

### Running the GUI

**Basic launch:**
```bash
python -m jarvis --gui
```

**With custom configuration:**
```bash
python -m jarvis --gui --config /path/to/config.yaml
```

**With debug logging:**
```bash
python -m jarvis --gui --debug
```

The GUI provides:
- **Dark/Light Theme**: Configurable theme for comfort during extended use
- **Intent Classification**: Automatic recognition of common commands for fast execution
- **Fast Actions**: Quick execution for simple recognized tasks
- **Full Planning**: Complex commands go through comprehensive LLM-based reasoning
- **Safety Controls**: Visual indicators for risky operations with approval workflow
- **Response Streaming**: Real-time display of LLM responses as they generate
- **Chat History**: Complete conversation history with export functionality

For detailed GUI features, see [GUI_MODE.md](GUI_MODE.md).

### Running the GUI with Voice Control

To enable voice control in the GUI, install the voice dependencies and launch with the `--voice` flag:

**Installation:**
```bash
# Core voice dependencies
pip install SpeechRecognition>=3.10.0 pvporcupine>=2.2.0

# Optional: PyAudio for advanced audio control
pip install pyaudio
```

**Launch with voice control:**
```bash
python -m jarvis --gui --voice
```

**Voice Control Features:**
- **Wake Word Detection**: Automatically listens for "Jarvis" (configurable)
- **Automatic STT**: Converts voice to text using Google Speech Recognition
- **Visual Feedback**: On-screen indicators show listening status
- **Seamless Integration**: Voice commands flow directly to the orchestrator
- **State Machine**: Wake word → STT → Controller processing

**Testing voice interface in isolation:**
```python
from jarvis.voice import VoiceInterface

vi = VoiceInterface(
    wakeword="jarvis",
    on_command=lambda cmd: print(f"Command: {cmd}"),
    on_error=lambda err: print(f"Error: {err}")
)

# Start listening
vi.start()

# Or inject text for testing (no microphone needed)
vi.inject_text("Jarvis turn on the lights")
```

**Troubleshooting voice:**
- Verify microphone is connected and working
- Check OS microphone permissions
- Ensure internet connection (Google Speech Recognition requires it)
- Try `vi.inject_text()` to test without microphone

For detailed voice features, see [GUI_MODE.md](GUI_MODE.md#voice-control-installation).

### Running the Interactive Chat Mode

**Basic usage:**
```bash
python -m jarvis --chat
```

**Short forms:**
```bash
python -m jarvis --interactive
python -m jarvis -i
```

For detailed chat mode features, see [CHAT_MODE.md](CHAT_MODE.md).

### Running the CLI

**Basic usage:**
```bash
python -m jarvis "what is the current time?"
```

**With configuration file:**
```bash
python -m jarvis --config config.yaml "list files on desktop"
```

**With debug logging:**
```bash
python -m jarvis --debug "help"
```

**Show version:**
```bash
python -m jarvis --version
```

**Show help:**
```bash
python -m jarvis --help
```

### Programmatic Usage

```python
from jarvis.container import Container

# Create DI container
container = Container()

# Get orchestrator
orchestrator = container.get_orchestrator()

# Initialize modules
orchestrator.initialize_modules()

# Execute command
result = orchestrator.handle_command("your command here")
print(result)
```

## Development

### Running Tests

**Run all tests:**
```bash
PYTHONPATH=/home/engine/project/src python -m pytest tests/ --tb=no -q
```

**Run with coverage report:**
```bash
pytest --cov=src/jarvis --cov-report=html
```

**Run specific test file:**
```bash
pytest tests/test_config.py -v
```

**Run tests matching pattern:**
```bash
pytest -k "test_config" -v
```

**Run expanded test suite for GUI and action features:**
```bash
# Run intent classification tests
PYTHONPATH=/home/engine/project/src python -m pytest tests/ -k "intent"

# Run action execution tests
PYTHONPATH=/home/engine/project/src python -m pytest tests/ -k "action"

# Run all GUI-related tests
PYTHONPATH=/home/engine/project/src python -m pytest tests/ -k "gui"

# Run streaming and chat tests
PYTHONPATH=/home/engine/project/src python -m pytest tests/ -k "chat or stream"
```

**Test Coverage Details:**
The expanded test suite includes:
- Configuration and setup tests
- CLI and argument parsing tests
- Orchestrator and command routing tests
- LLM client and integration tests
- Reasoning module and plan generation tests
- Tool teaching and knowledge extraction tests
- Chat session and streaming tests
- Intent classification tests
- Action execution and safety tests
- Persistent memory and storage tests

### Code Quality

**Format code:**
```bash
black src/ tests/
isort src/ tests/
```

**Lint code:**
```bash
flake8 src/ tests/
```

**Type checking:**
```bash
mypy src/
```

**Run all checks:**
```bash
black src/ tests/ --check
isort src/ tests/ --check-only
flake8 src/ tests/
mypy src/
pytest --cov=src/jarvis
```

## Architecture

### Core Components

1. **CLI (`cli.py`)**
   - Argument parsing for natural language commands
   - Entry point for the application
   - Handles initialization and error handling

2. **Configuration (`config.py`)**
   - `JarvisConfig`: Main configuration model
   - `LLMConfig`: LLM provider settings
   - `SafetyConfig`: Safety feature toggles
   - `StorageConfig`: Storage path configuration
   - `ConfigLoader`: Loads from YAML/JSON files

3. **Dependency Injection (`container.py`)**
   - `Container`: Manages component lifecycle and dependencies
   - Caches instances for reuse
   - Handles logging setup

4. **Orchestrator (`orchestrator.py`)**
   - Central command router
   - Coordinates between modules
   - Handles command execution

5. **Logging (`logging_config.py`)**
   - Configurable logging setup
   - Console and file handlers
   - Rotating file handler for log management

### Module Design

The architecture emphasizes:
- **Loose Coupling**: Components interact through defined interfaces
- **Dependency Injection**: Dependencies provided via Container
- **Type Safety**: Full type hints throughout
- **Testability**: Each component independently testable with mocks
- **Extensibility**: Easy to add new modules and features

## Testing

### Test Coverage

The test suite covers:
- Configuration loading from YAML/JSON files
- Configuration validation and defaults
- CLI argument parsing
- Command routing through orchestrator
- Dependency injection and component lifecycle
- Error handling and edge cases

### Running Tests with Coverage

```bash
pytest --cov=src/jarvis --cov-report=term-missing --cov-report=html
```

Coverage reports are generated in:
- Terminal: `--cov-report=term-missing`
- HTML: `htmlcov/index.html`

## Logging

Logs are configured automatically based on the configuration:
- **Console**: All INFO level and above (DEBUG if --debug flag used)
- **File**: Stored in logs directory with rotation
  - Max size: 10 MB per file
  - Backup count: 5 files

### Log Format

```
2024-01-15 10:30:45 - jarvis.cli - INFO - Command executed successfully
```

## System Actions

Jarvis includes a comprehensive system actions framework that provides structured access to system-level operations:

### Available Action Categories

1. **File Operations** (`files.py`)
   - List, create, delete, move, copy files and directories
   - Get file information and metadata
   - Enforces directory allowlist/denylist for security

2. **GUI Control** (`gui_control.py`)
   - Mouse movement and clicking
   - Screen capture
   - Get screen dimensions and mouse position
   - Uses `pyautogui` with safety failsafes

3. **Text Typing** (`typing.py`)
   - Type text using keyboard simulation
   - Press individual keys and key combinations
   - Clipboard operations (copy/paste)
   - Uses `pyautogui` and `pyperclip`

4. **Windows Registry** (`registry.py`)
   - Read, write, delete registry values
   - List registry subkeys and values
   - Windows-only functionality using `winreg`

5. **OCR (Optical Character Recognition)** (`ocr.py`)
   - Extract text from images and screenshots
   - Bounding box information for text locations
   - Uses `pytesseract` and Windows OCR APIs
   - Configurable language support

6. **PowerShell** (`powershell.py`)
   - Execute PowerShell commands and scripts
   - Get system information, processes, services
   - File hash calculation
   - Cross-platform PowerShell Core support

7. **Subprocess** (`subprocess_actions.py`)
   - Execute system commands
   - Open applications
   - Network operations (ping, interfaces)
   - Process management

### Using System Actions

The `SystemActionRouter` provides a unified interface:

```python
from jarvis.system_actions import SystemActionRouter

# Initialize router
router = SystemActionRouter(dry_run=True)

# Route actions
result = router.route_action("file_list", directory="/tmp")
result = router.route_action("gui_click_mouse", x=100, y=100)
result = router.route_action("powershell_execute", command="Get-Process")
```

### Configuration

Add to your `config.yaml`:

```yaml
# Execution settings
execution:
  allowed_directories:
    - ~/Documents
    - ~/Desktop
  disallowed_directories:
    - /etc
    - /sys
  dry_run: false
  action_timeout: 30
  # Verification and retry settings
  enable_verification: true      # Verify side effects after actions
  max_retries: 3                 # Maximum retry attempts on failure
  retry_backoff_seconds: 1.0     # Base backoff time (exponential)
  retry_alternatives:            # Optional fallback action mappings
    file_create: powershell_execute
    file_delete: powershell_execute

# OCR settings
ocr:
  tesseract_path: ""  # Path to tesseract executable
  default_language: eng
  confidence_threshold: 60.0
```

### Safety Features

- **Dry-run mode**: Preview actions without executing
- **Directory restrictions**: Allowlist/denylist for file operations
- **Timeout protection**: Prevent hanging operations
- **Structured results**: All actions return `ActionResult` objects
- **Error handling**: Graceful failure with actionable error messages
- **Side-effect verification**: Verify actions actually completed (files exist, etc.)
- **Automatic retries**: Exponential backoff retry on execution/verification failure
- **Alternative actions**: Fallback to secondary action methods when primary fails

### Dependencies

Install optional dependencies for specific features:

```bash
# GUI control and typing
pip install pyautogui pyperclip

# OCR functionality
pip install pytesseract pillow

# Windows registry (Windows only)
# Built-in winreg module

# PowerShell (cross-platform)
pip install pwsh  # PowerShell Core
```

## Future Extensions

This skeleton is designed to be extended with:
- Actual LLM integration
- Natural language processing modules
- Command execution modules
- Plugin system
- Database storage layer
- API server
- GUI interface

## License

Specify your project license here.

## Contributing

Specify contribution guidelines here.
