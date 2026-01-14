"""
Process controller utility for executing subprocesses with timeout and logging.

Provides cross-platform process management with timeout detection,
stdout/stderr capture, and graceful termination of process trees.
"""

import logging
import signal
import subprocess
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional

logger = logging.getLogger(__name__)


@dataclass
class ProcessResult:
    """Result of a subprocess execution."""
    exit_code: int
    stdout: str
    stderr: str
    timed_out: bool
    duration_seconds: float
    signal: Optional[int]


class ProcessController:
    """
    Executes subprocesses with configurable timeout and output capture.
    
    Features:
    - Live output capture to log files
    - Timeout detection and graceful kill
    - Windows + Unix compatibility
    - No hanging on modal dialogs
    """

    def __init__(self) -> None:
        """Initialize process controller."""
        try:
            import psutil
            self.psutil = psutil
        except ImportError:
            logger.warning("psutil not available, using fallback process management")
            self.psutil = None

    def run_subprocess(
        self,
        cmd: List[str],
        cwd: str,
        timeout: int,
        log_file: Optional[Path] = None,
    ) -> ProcessResult:
        """
        Execute subprocess with timeout and capture output.

        Args:
            cmd: Command and arguments to execute
            cwd: Working directory for subprocess
            timeout: Timeout in seconds
            log_file: Optional path to write live output log

        Returns:
            ProcessResult with execution details
        """
        start_time = time.time()
        log_file = log_file or Path.cwd() / "process_log.txt"
        
        logger.info(f"Running subprocess: {' '.join(cmd)}")
        logger.info(f"Working directory: {cwd}")
        logger.info(f"Timeout: {timeout}s")
        logger.info(f"Log file: {log_file}")

        try:
            # Create log directory
            log_file.parent.mkdir(parents=True, exist_ok=True)
            
            # Prepare process creation flags
            creation_flags = 0
            if sys.platform == "win32":
                creation_flags = subprocess.CREATE_NEW_PROCESS_GROUP

            # Start process
            process = subprocess.Popen(
                cmd,
                cwd=cwd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1,
                creationflags=creation_flags,
            )

            stdout_lines = []
            stderr_lines = []
            
            with open(log_file, "w", encoding="utf-8") as log_f:
                log_f.write(f"Command: {' '.join(cmd)}\n")
                log_f.write(f"Working directory: {cwd}\n")
                log_f.write(f"Started at: {time.strftime('%Y-%m-%d %H:%M:%S')}\n")
                log_f.write("=" * 50 + "\n\n")

                # Stream output in real-time
                while True:
                    # Check if process has terminated
                    exit_code = process.poll()
                    if exit_code is not None:
                        # Process finished, read any remaining output
                        remaining_output = process.stdout.read()
                        if remaining_output:
                            lines = remaining_output.splitlines(keepends=True)
                            for line in lines:
                                stdout_lines.append(line)
                                log_f.write(line)
                        break

                    # Read available output
                    try:
                        line = process.stdout.readline()
                        if line:
                            stdout_lines.append(line)
                            log_f.write(line)
                            log_f.flush()
                        else:
                            time.sleep(0.1)  # Brief pause to avoid busy waiting
                    except Exception as e:
                        logger.warning(f"Error reading process output: {e}")
                        break

            duration = time.time() - start_time
            logger.info(f"Process completed in {duration:.2f}s with exit code {exit_code}")

            return ProcessResult(
                exit_code=exit_code,
                stdout="".join(stdout_lines),
                stderr="".join(stderr_lines),
                timed_out=False,
                duration_seconds=duration,
                signal=None,
            )

        except subprocess.TimeoutExpired:
            duration = time.time() - start_time
            logger.warning(f"Process timed out after {timeout}s")
            
            # Kill process tree
            self._kill_process_tree(process.pid)
            
            return ProcessResult(
                exit_code=-1,
                stdout="".join(stdout_lines),
                stderr="TimeoutExpired",
                timed_out=True,
                duration_seconds=duration,
                signal=None,
            )

        except Exception as e:
            duration = time.time() - start_time
            logger.error(f"Subprocess execution failed: {e}")
            
            # Kill process if still running
            if 'process' in locals():
                self._kill_process_tree(process.pid)
            
            return ProcessResult(
                exit_code=-1,
                stdout="".join(stdout_lines),
                stderr=str(e),
                timed_out=False,
                duration_seconds=duration,
                signal=None,
            )

    def run_with_stdin(
        self,
        cmd: List[str],
        stdin_data: str,
        cwd: str,
        timeout: int,
    ) -> ProcessResult:
        """
        Execute subprocess with stdin data.

        Args:
            cmd: Command and arguments
            stdin_data: Data to send to stdin
            cwd: Working directory
            timeout: Timeout in seconds

        Returns:
            ProcessResult with execution details
        """
        start_time = time.time()
        
        logger.info(f"Running subprocess with stdin: {' '.join(cmd)}")
        logger.info(f"Stdin data: {stdin_data[:100]}...")

        try:
            creation_flags = 0
            if sys.platform == "win32":
                creation_flags = subprocess.CREATE_NEW_PROCESS_GROUP

            process = subprocess.Popen(
                cmd,
                cwd=cwd,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                creationflags=creation_flags,
            )

            # Send stdin data
            process.stdin.write(stdin_data)
            process.stdin.flush()
            process.stdin.close()

            # Wait for completion with timeout
            try:
                stdout, stderr = process.communicate(timeout=timeout)
                exit_code = process.returncode
                duration = time.time() - start_time
                
                logger.info(f"Process completed with exit code {exit_code}")
                
                return ProcessResult(
                    exit_code=exit_code,
                    stdout=stdout or "",
                    stderr=stderr or "",
                    timed_out=False,
                    duration_seconds=duration,
                    signal=None,
                )

            except subprocess.TimeoutExpired:
                duration = time.time() - start_time
                logger.warning(f"Process timed out after {timeout}s")
                
                self._kill_process_tree(process.pid)
                
                return ProcessResult(
                    exit_code=-1,
                    stdout="",
                    stderr="TimeoutExpired",
                    timed_out=True,
                    duration_seconds=duration,
                    signal=None,
                )

        except Exception as e:
            duration = time.time() - start_time
            logger.error(f"Subprocess with stdin failed: {e}")
            
            if 'process' in locals():
                self._kill_process_tree(process.pid)
            
            return ProcessResult(
                exit_code=-1,
                stdout="",
                stderr=str(e),
                timed_out=False,
                duration_seconds=duration,
                signal=None,
            )

    def _kill_process_tree(self, pid: int) -> None:
        """
        Kill process and all children.

        Args:
            pid: Process ID to terminate
        """
        try:
            if self.psutil:
                # Use psutil for robust process tree termination
                try:
                    parent = self.psutil.Process(pid)
                    children = parent.children(recursive=True)
                    
                    logger.info(f"Killing process tree: PID {pid} with {len(children)} children")
                    
                    # Kill all children first
                    for child in children:
                        try:
                            child.kill()
                        except (psutil.NoSuchProcess, psutil.AccessDenied):
                            pass
                    
                    # Kill parent
                    parent.kill()
                    
                except (psutil.NoSuchProcess, psutil.AccessDenied) as e:
                    logger.warning(f"psutil failed to kill process {pid}: {e}")
                    # Fall back to system command
                    self._fallback_kill(pid)
            else:
                # Fallback without psutil
                self._fallback_kill(pid)
                
        except Exception as e:
            logger.error(f"Failed to kill process tree {pid}: {e}")

    def _fallback_kill(self, pid: int) -> None:
        """
        Fallback process killing without psutil.

        Args:
            pid: Process ID to terminate
        """
        try:
            if sys.platform == "win32":
                # Windows: use taskkill
                import subprocess
                subprocess.run(
                    ["taskkill", "/F", "/T", "/PID", str(pid)],
                    capture_output=True,
                    timeout=5,
                )
            else:
                # Unix: use kill with process group
                import os
                try:
                    os.killpg(os.getpgid(pid), signal.SIGKILL)
                except ProcessLookupError:
                    pass  # Process already dead
                    
        except Exception as e:
            logger.warning(f"Fallback kill failed for PID {pid}: {e}")