# File Operations Tool

A comprehensive tool for managing file operations on the system.

## Overview

The File Operations Tool provides a unified interface for reading, writing, and managing files with safety checks and error handling.

## Commands

### read
Read and display the contents of a file.

**Syntax:** `read <file_path> [encoding]`

**Parameters:**
- `file_path` (required): Path to the file to read
- `encoding` (optional): File encoding (default: utf-8)

**Examples:**
- `read /home/user/documents/report.txt`
- `read /home/user/data.json utf-8`

### write
Write or append content to a file.

**Syntax:** `write <file_path> <content> [mode]`

**Parameters:**
- `file_path` (required): Path to the file
- `content` (required): Content to write
- `mode` (optional): Write mode - 'w' (overwrite) or 'a' (append), default is 'w'

**Examples:**
- `write /tmp/output.txt "Hello World"`
- `write /tmp/log.txt "New entry" append`

### delete
Delete a file from the system.

**Syntax:** `delete <file_path> [force]`

**Parameters:**
- `file_path` (required): Path to the file to delete
- `force` (optional): Force deletion without confirmation (boolean, default: false)

**Examples:**
- `delete /tmp/temp_file.txt`
- `delete /home/user/old_data.backup force`

## Usage Constraints

- File paths must be absolute or relative to current working directory
- File size limit: 100MB per operation
- Reading/writing protected system files requires elevated privileges
- Maximum file name length: 255 characters
- Supported file types: text files, JSON, YAML, CSV, binary files

## Error Handling

- FileNotFoundError: Raised when file does not exist
- PermissionError: Raised when insufficient privileges to access file
- IOError: Raised for other I/O related errors
- ValueError: Raised for invalid parameters

## Usage Examples

### Reading a file
```
read /home/user/config.yaml
```

### Writing to a new file
```
write /tmp/output.txt "Configuration complete"
```

### Appending to existing file
```
write /var/log/app.log "Application started" append
```

### Deleting a temporary file
```
delete /tmp/temp_data.tmp
```

## Performance Notes

- Reading large files (>10MB) may take several seconds
- Writing operations are atomic when supported by filesystem
- File operations are not parallelizable
- Consider using batching for multiple file operations
