# Persistent Memory Module

## Overview

The Persistent Memory Module (`persistent_memory.py`) provides a comprehensive, pluggable storage layer for persisting application state across sessions. It enables Jarvis to remember user preferences, past tasks, device information, and learned tool metadata with full CRUD capabilities and rich query support.

## Architecture

### Core Components

1. **StorageBackend (Abstract Base Class)**
   - Defines the interface for storage implementations
   - Decouples application logic from storage details
   - Enables pluggable storage backends

2. **SQLiteBackend**
   - Robust SQL-based persistent storage
   - Optimized for production use
   - Supports complex queries with indexes
   - Located in `sqlite_backend.py`

3. **JSONBackend**
   - Lightweight file-based storage
   - Ideal for development and testing
   - Simpler deployment without database dependencies
   - Located in `json_backend.py`

4. **MemoryModule**
   - High-level API for memory management
   - Automatic backend selection and initialization
   - Category-based organization (preferences, tasks, devices)
   - Contextual retrieval by tags, entities, and semantic keys

## Memory Entry Structure

Each memory entry contains:

```python
MemoryEntry(
    id: str                      # Unique identifier (auto-generated UUID)
    category: str                # preferences, tasks, devices, tools, etc.
    key: str                     # Semantic key for lookup
    value: Dict[str, Any]        # Flexible data structure
    tags: List[str]              # For flexible retrieval
    entity_type: str             # task, tool, device, user_preference, etc.
    entity_id: Optional[str]     # Specific entity identifier
    timestamp: datetime          # When created/updated
    provenance: Dict[str, str]   # Module name, task_id, created_at, updated_by
)
```

## API Usage

### Initialization

```python
from jarvis.persistent_memory import MemoryModule
from pathlib import Path

# Using SQLite (default)
memory = MemoryModule(
    storage_dir=Path.home() / ".jarvis" / "memory",
    backend_type="sqlite"  # or "json"
)

# Bootstrap on startup
memory.bootstrap()
```

### Creating Memories

```python
# Create a preference
memory_id = memory.create_memory(
    category="preferences",
    key="theme",
    value={"mode": "dark"},
    entity_type="user_preference",
    tags=["ui", "important"],
    module="ui_module",
    task_id="task_123"
)

# Create a task record
memory_id = memory.record_task(
    task_id="task_1",
    task_data={"status": "completed", "duration": 45},
    tags=["executed"]
)

# Set device info
memory.set_device_info({"name": "laptop", "os": "linux"})
```

### Reading Memories

```python
# By ID
entry = memory.get_memory(memory_id)

# By semantic key
entry = memory.get_memory_by_key("theme")

# By category
preferences = memory.get_memories_by_category("preferences")

# By entity
tasks = memory.get_memories_by_entity("task", entity_id="task_123")

# By tags
important = memory.get_memories_by_tags(["important"])

# Search with filters
results = memory.search_memories(
    category="preferences",
    entity_type="user_preference",
    tags=["ui"]
)
```

### Updating Memories

```python
success = memory.update_memory(
    memory_id=memory_id,
    value={"mode": "light"},
    tags=["ui", "updated"],
    module="ui_module"
)
```

### Deleting Memories

```python
success = memory.delete_memory(memory_id)

# Clear all (use with caution)
memory.clear_all()
```

### Convenience APIs

```python
# User preferences
memory.set_user_preference("theme", {"mode": "dark"})
prefs = memory.get_user_preferences()

# Device info
memory.set_device_info({"name": "laptop", "os": "linux"})
device = memory.get_device_info()

# Task history
tasks = memory.get_task_history(limit=10)
```

### Shutdown

```python
# Gracefully shutdown (flushes buffered data)
memory.shutdown()
```

## Integration with Container

The `MemoryModule` is integrated with the DI container for automatic initialization:

```python
from jarvis.container import Container

container = Container()
memory_module = container.get_memory_module()

# Module is cached and reused across the application
```

## Storage Backends

### SQLite Backend

**Features:**
- Transaction support for data consistency
- Indexed queries for efficient retrieval
- Automatic table creation and schema management
- Suitable for production deployments

**Performance Characteristics:**
- Write: O(1) average
- Query: O(log n) with indexes
- Concurrent access supported via SQLite's locking

**File Location:** `~/.jarvis/memory/memory.db`

### JSON Backend

**Features:**
- Simple human-readable format
- No external dependencies
- Ideal for development and testing
- Easy to inspect and debug

**Performance Characteristics:**
- Write: O(n) - full file rewrite
- Query: O(n) - in-memory filtering
- Best for < 1000 entries

**File Location:** `~/.jarvis/memory/memory.json`

## Provenance Tracking

Every memory entry includes provenance information:

```python
entry.provenance = {
    "module": "ui_module",        # Which module created it
    "task_id": "task_123",         # Associated task
    "created_at": "2024-01-15T10:30:00",
    "updated_by": "task_executor", # Which module updated it (if applicable)
    "updated_at": "2024-01-15T11:00:00"
}
```

This enables:
- Auditing: Track what changed and when
- Debugging: Identify which module modified data
- Context: Link memories to specific tasks

## Persistence Across Sessions

Memories persist automatically across application restarts:

```python
# Session 1
memory = MemoryModule()
memory.set_user_preference("theme", {"mode": "dark"})
memory.shutdown()

# Session 2 (after restart)
memory = MemoryModule()
prefs = memory.get_user_preferences()  # {"theme": {"mode": "dark"}}
```

## Contextual Retrieval

Retrieve memories efficiently using various filters:

```python
# By category
all_tasks = memory.search_memories(category="tasks")

# By entity type and ID
task_123_memories = memory.search_memories(
    entity_type="task",
    entity_id="123"
)

# By multiple tags (any match)
urgent = memory.search_memories(tags=["urgent", "important"])

# Complex queries
memories = memory.search_memories(
    category="tasks",
    entity_type="task",
    tags=["executed"],
    key="task_summary"
)
```

## Testing

Comprehensive tests cover:

1. **Backend Tests** (`test_persistent_memory.py`)
   - SQLite backend CRUD operations
   - JSON backend CRUD operations
   - Query functionality
   - Persistence across instances
   - Data type preservation

2. **Module Tests**
   - High-level API functionality
   - Category management
   - Entity tracking
   - Tag-based retrieval
   - Provenance tracking

3. **Integration Tests** (`test_memory_module_integration.py`)
   - Container integration
   - Multi-session persistence
   - Cross-backend compatibility
   - Full workflow scenarios

Run tests with:
```bash
pytest tests/test_persistent_memory.py -v
pytest tests/test_memory_module_integration.py -v
```

## Best Practices

1. **Use Semantic Keys**
   ```python
   # Good: Descriptive and unique
   memory.create_memory(key="user_theme_preference", ...)
   
   # Avoid: Generic or unclear
   memory.create_memory(key="pref", ...)
   ```

2. **Tag Appropriately**
   ```python
   # Tags should be lowercase and descriptive
   tags=["ui", "user-preference", "important"]
   ```

3. **Track Provenance**
   ```python
   # Always provide module name
   memory.create_memory(
       ...,
       module="module_name",
       task_id="task_id"
   )
   ```

4. **Clean Up Periodically**
   ```python
   # Archive or delete old entries
   old_tasks = memory.search_memories(
       category="tasks",
       tags=["archived"]
   )
   for task in old_tasks:
       memory.delete_memory(task.id)
   ```

5. **Choose Backend Wisely**
   - **SQLite**: Production, > 1000 entries, complex queries
   - **JSON**: Development, testing, < 1000 entries

## Examples

### Example 1: User Preferences Management

```python
def save_user_settings(memory: MemoryModule, settings: Dict):
    """Save user settings across sessions."""
    for key, value in settings.items():
        memory.set_user_preference(key, value)
    memory.shutdown()

def load_user_settings(memory: MemoryModule) -> Dict:
    """Load previously saved user settings."""
    return memory.get_user_preferences()
```

### Example 2: Task Tracking

```python
def execute_task(memory: MemoryModule, task_id: str, task_fn):
    """Execute and track a task."""
    try:
        result = task_fn()
        memory.record_task(
            task_id=task_id,
            task_data={
                "status": "completed",
                "result": result
            },
            tags=["executed"]
        )
    except Exception as e:
        memory.record_task(
            task_id=task_id,
            task_data={
                "status": "failed",
                "error": str(e)
            },
            tags=["failed"]
        )
```

### Example 3: Tool Knowledge

```python
def learn_tool(memory: MemoryModule, tool_name: str, tool_info: Dict):
    """Store learned tool capabilities."""
    memory.create_memory(
        category="tools",
        key=f"tool_{tool_name}",
        value=tool_info,
        entity_type="tool",
        entity_id=tool_name,
        tags=["learned", "tool"],
        module="tool_teaching_module"
    )

def recall_tool(memory: MemoryModule, tool_name: str):
    """Retrieve learned tool information."""
    return memory.get_memory_by_key(f"tool_{tool_name}")
```

## Configuration

The memory storage location can be configured through the main Jarvis config:

```yaml
# ~/.jarvis/config.yaml
storage:
  data_dir: ~/.jarvis/data
  # Persistent memory stored in: ~/.jarvis/data/persistent_memory/
```

## Troubleshooting

### Q: "No module named 'sqlite3'"
**A:** sqlite3 is included in Python standard library. Ensure Python installation is complete.

### Q: Memory entries not persisting
**A:** Call `memory.shutdown()` to flush buffered data before exit.

### Q: Slow queries with JSON backend
**A:** Switch to SQLite backend for better performance: `MemoryModule(backend_type="sqlite")`

### Q: Database locked error
**A:** Ensure only one process accesses the SQLite database at a time.

## Future Enhancements

- [ ] Encryption at rest for sensitive data
- [ ] Automatic cleanup policies (TTL)
- [ ] Memory compression for large datasets
- [ ] PostgreSQL backend for multi-process scenarios
- [ ] Query optimization and caching
- [ ] Memory analytics and reporting
