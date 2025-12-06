"""
Subprocess system action module.

Provides general subprocess command execution while enforcing
dry-run semantics and safety checks.
"""

import logging
import subprocess
import sys
from typing import Dict, List, Optional, Union

from jarvis.action_executor import ActionResult

logger = logging.getLogger(__name__)


class SubprocessActions:
    """
    Subprocess system actions.

    Executes system commands through subprocess with dry-run support
    and proper error handling.
    """

    def __init__(self, dry_run: bool = False, timeout: int = 30) -> None:
        """
        Initialize subprocess actions.

        Args:
            dry_run: If True, preview commands without executing
            timeout: Command timeout in seconds
        """
        self.dry_run = dry_run
        self.timeout = timeout
        logger.info("SubprocessActions initialized")

    def execute_command(
        self,
        command: Union[str, List[str]],
        shell: bool = True,
        capture_output: bool = True,
        working_directory: Optional[str] = None,
        env: Optional[Dict[str, str]] = None
    ) -> ActionResult:
        """
        Execute a system command.

        Args:
            command: Command to execute (string or list)
            shell: Whether to use shell execution
            capture_output: Whether to capture stdout/stderr
            working_directory: Working directory for command execution
            env: Environment variables for command

        Returns:
            ActionResult with command output or error
        """
        cmd_str = command if isinstance(command, str) else ' '.join(command)
        logger.info(f"Executing command: {cmd_str[:100]}...")
        
        if self.dry_run:
            return ActionResult(
                success=True,
                action_type="execute_command",
                message=f"[DRY-RUN] Would execute: {cmd_str}",
                data={
                    "command": command,
                    "shell": shell,
                    "capture_output": capture_output,
                    "working_directory": working_directory,
                    "env": env,
                    "dry_run": True
                },
                execution_time_ms=0.0
            )

        try:
            if capture_output:
                result = subprocess.run(
                    command,
                    shell=shell,
                    capture_output=True,
                    text=True,
                    timeout=self.timeout,
                    cwd=working_directory,
                    env=env
                )
                
                stdout = result.stdout.strip() if result.stdout else ""
                stderr = result.stderr.strip() if result.stderr else ""
                
                return ActionResult(
                    success=result.returncode == 0,
                    action_type="execute_command",
                    message=f"Command executed with return code {result.returncode}",
                    data={
                        "command": command,
                        "shell": shell,
                        "return_code": result.returncode,
                        "stdout": stdout,
                        "stderr": stderr,
                        "working_directory": working_directory,
                        "success": result.returncode == 0
                    },
                    error=stderr if result.returncode != 0 else None
                )
            else:
                # For non-captured output, run without capture
                process = subprocess.Popen(
                    command,
                    shell=shell,
                    stdout=None,
                    stderr=None,
                    cwd=working_directory,
                    env=env
                )
                
                process.wait(timeout=self.timeout)
                
                return ActionResult(
                    success=process.returncode == 0,
                    action_type="execute_command",
                    message=f"Command executed with return code {process.returncode}",
                    data={
                        "command": command,
                        "shell": shell,
                        "return_code": process.returncode,
                        "capture_output": False,
                        "working_directory": working_directory
                    }
                )
                
        except subprocess.TimeoutExpired:
            logger.error(f"Command timed out: {cmd_str}")
            return ActionResult(
                success=False,
                action_type="execute_command",
                message="Command timed out",
                error=f"Command exceeded timeout of {self.timeout} seconds"
            )
        except Exception as e:
            logger.error(f"Error executing command: {e}")
            return ActionResult(
                success=False,
                action_type="execute_command",
                message="Failed to execute command",
                error=str(e)
            )

    def open_application(self, application_path: str, arguments: Optional[str] = None) -> ActionResult:
        """
        Open an application with optional arguments.

        Args:
            application_path: Path to the application executable
            arguments: Optional command line arguments

        Returns:
            ActionResult indicating success or failure
        """
        logger.info(f"Opening application: {application_path}")
        
        if self.dry_run:
            return ActionResult(
                success=True,
                action_type="open_application",
                message=f"[DRY-RUN] Would open application: {application_path}",
                data={
                    "application_path": application_path,
                    "arguments": arguments,
                    "dry_run": True
                }
            )

        try:
            if sys.platform == "win32":
                # On Windows, use os.startfile for simple cases
                if not arguments:
                    import os
                    os.startfile(application_path)
                    return ActionResult(
                        success=True,
                        action_type="open_application",
                        message=f"Opened application: {application_path}",
                        data={"application_path": application_path, "arguments": arguments}
                    )
                else:
                    # With arguments, use subprocess
                    command = f'"{application_path}" {arguments}'
            elif sys.platform == "darwin":
                # On macOS, use open command
                command = f'open "{application_path}"'
                if arguments:
                    command += f" --args {arguments}"
            else:
                # On Linux, just execute directly
                command = f'"{application_path}"'
                if arguments:
                    command += f" {arguments}"

            result = subprocess.run(command, shell=True, timeout=self.timeout)
            
            return ActionResult(
                success=result.returncode == 0,
                action_type="open_application",
                message=f"Opened application: {application_path}",
                data={
                    "application_path": application_path,
                    "arguments": arguments,
                    "return_code": result.returncode
                }
            )
            
        except Exception as e:
            logger.error(f"Error opening application: {e}")
            return ActionResult(
                success=False,
                action_type="open_application",
                message="Failed to open application",
                error=str(e)
            )

    def ping_host(self, host: str, count: int = 4) -> ActionResult:
        """
        Ping a host to check connectivity.

        Args:
            host: Host to ping
            count: Number of ping packets to send

        Returns:
            ActionResult with ping results or error
        """
        logger.info(f"Pinging host: {host}")
        
        if sys.platform == "win32":
            command = f"ping -n {count} {host}"
        else:
            command = f"ping -c {count} {host}"
        
        return self.execute_command(command, shell=True, capture_output=True)

    def get_network_interfaces(self) -> ActionResult:
        """
        Get network interface information.

        Returns:
            ActionResult with network interface data or error
        """
        logger.info("Getting network interfaces")
        
        if sys.platform == "win32":
            command = "ipconfig /all"
        elif sys.platform == "darwin":
            command = "ifconfig -a"
        else:
            command = "ip addr show"
        
        return self.execute_command(command, shell=True, capture_output=True)

    def get_disk_usage(self, path: str = ".") -> ActionResult:
        """
        Get disk usage information for a path.

        Args:
            path: Path to check disk usage for

        Returns:
            ActionResult with disk usage data or error
        """
        logger.info(f"Getting disk usage for: {path}")
        
        if sys.platform == "win32":
            command = f'dir "{path}" /-c'
        else:
            command = f"du -sh '{path}'"
        
        return self.execute_command(command, shell=True, capture_output=True)

    def get_environment_variables(self) -> ActionResult:
        """
        Get environment variables.

        Returns:
            ActionResult with environment variables or error
        """
        logger.info("Getting environment variables")
        
        if sys.platform == "win32":
            command = "set"
        else:
            command = "env"
        
        return self.execute_command(command, shell=True, capture_output=True)

    def kill_process(self, process_id: int, force: bool = False) -> ActionResult:
        """
        Kill a process by ID.

        Args:
            process_id: Process ID to kill
            force: Whether to force kill the process

        Returns:
            ActionResult indicating success or failure
        """
        logger.info(f"Killing process: {process_id}")
        
        if sys.platform == "win32":
            command = f"taskkill /PID {process_id}"
            if force:
                command += " /F"
        else:
            command = f"kill {process_id}"
            if force:
                command = f"kill -9 {process_id}"
        
        return self.execute_command(command, shell=True, capture_output=True)

    def list_processes(self) -> ActionResult:
        """
        List running processes.

        Returns:
            ActionResult with process list or error
        """
        logger.info("Listing processes")
        
        if sys.platform == "win32":
            command = "tasklist"
        else:
            command = "ps aux"
        
        return self.execute_command(command, shell=True, capture_output=True)