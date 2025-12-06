"""
PowerShell system action module.

Provides PowerShell command execution through subprocess while enforcing
dry-run semantics and safety checks.
"""

import logging
import subprocess
import sys
from typing import Dict, List, Optional, Union

from jarvis.action_executor import ActionResult

logger = logging.getLogger(__name__)


class PowerShellActions:
    """
    PowerShell system actions.

    Executes PowerShell commands through subprocess with dry-run support
    and proper error handling.
    """

    def __init__(self, dry_run: bool = False, timeout: int = 30) -> None:
        """
        Initialize PowerShell actions.

        Args:
            dry_run: If True, preview commands without executing
            timeout: Command timeout in seconds
        """
        self.dry_run = dry_run
        self.timeout = timeout
        self.powershell_cmd = self._get_powershell_command()
        logger.info("PowerShellActions initialized")

    def _get_powershell_command(self) -> List[str]:
        """
        Get the appropriate PowerShell command for the current platform.

        Returns:
            List of command parts to execute PowerShell
        """
        if sys.platform == "win32":
            # On Windows, try powershell.exe first, then fallback to pwsh.exe
            try:
                subprocess.run(["powershell.exe", "-Command", "Get-Host"], 
                             capture_output=True, timeout=5, check=True)
                return ["powershell.exe", "-Command", "-"]
            except (subprocess.CalledProcessError, subprocess.TimeoutExpired, FileNotFoundError):
                try:
                    subprocess.run(["pwsh.exe", "-Command", "Get-Host"], 
                                 capture_output=True, timeout=5, check=True)
                    return ["pwsh.exe", "-Command", "-"]
                except (subprocess.CalledProcessError, subprocess.TimeoutExpired, FileNotFoundError):
                    return ["powershell.exe", "-Command", "-"]  # Fallback
        else:
            # On non-Windows, try pwsh (PowerShell Core)
            try:
                subprocess.run(["pwsh", "-Command", "Get-Host"], 
                             capture_output=True, timeout=5, check=True)
                return ["pwsh", "-Command", "-"]
            except (subprocess.CalledProcessError, subprocess.TimeoutExpired, FileNotFoundError):
                return ["pwsh", "-Command", "-"]  # Fallback

    def execute_command(
        self, 
        command: str, 
        capture_output: bool = True,
        shell: bool = False
    ) -> ActionResult:
        """
        Execute a PowerShell command.

        Args:
            command: PowerShell command to execute
            capture_output: Whether to capture stdout/stderr
            shell: Whether to use shell execution

        Returns:
            ActionResult with command output or error
        """
        logger.info(f"Executing PowerShell command: {command[:100]}...")
        
        if self.dry_run:
            return ActionResult(
                success=True,
                action_type="execute_command",
                message=f"[DRY-RUN] Would execute: {command}",
                data={
                    "command": command,
                    "capture_output": capture_output,
                    "shell": shell,
                    "dry_run": True
                },
                execution_time_ms=0.0
            )

        try:
            if capture_output:
                result = subprocess.run(
                    self.powershell_cmd + [command],
                    capture_output=True,
                    text=True,
                    timeout=self.timeout,
                    input=command if not shell else None
                )
                
                stdout = result.stdout.strip() if result.stdout else ""
                stderr = result.stderr.strip() if result.stderr else ""
                
                return ActionResult(
                    success=result.returncode == 0,
                    action_type="execute_command",
                    message=f"PowerShell command executed with return code {result.returncode}",
                    data={
                        "command": command,
                        "return_code": result.returncode,
                        "stdout": stdout,
                        "stderr": stderr,
                        "success": result.returncode == 0
                    },
                    error=stderr if result.returncode != 0 else None
                )
            else:
                # For non-captured output, run without capture
                process = subprocess.Popen(
                    self.powershell_cmd + [command],
                    stdin=subprocess.PIPE if not shell else None,
                    stdout=None,
                    stderr=None,
                    text=True
                )
                
                if not shell:
                    process.communicate(input=command, timeout=self.timeout)
                else:
                    process.wait(timeout=self.timeout)
                
                return ActionResult(
                    success=process.returncode == 0,
                    action_type="execute_command",
                    message=f"PowerShell command executed with return code {process.returncode}",
                    data={
                        "command": command,
                        "return_code": process.returncode,
                        "capture_output": False
                    }
                )
                
        except subprocess.TimeoutExpired:
            logger.error(f"PowerShell command timed out: {command}")
            return ActionResult(
                success=False,
                action_type="execute_command",
                message="PowerShell command timed out",
                error=f"Command exceeded timeout of {self.timeout} seconds"
            )
        except Exception as e:
            logger.error(f"Error executing PowerShell command: {e}")
            return ActionResult(
                success=False,
                action_type="execute_command",
                message="Failed to execute PowerShell command",
                error=str(e)
            )

    def execute_script(self, script_content: str) -> ActionResult:
        """
        Execute a PowerShell script.

        Args:
            script_content: PowerShell script content to execute

        Returns:
            ActionResult with script output or error
        """
        logger.info(f"Executing PowerShell script ({len(script_content)} characters)")
        
        if self.dry_run:
            return ActionResult(
                success=True,
                action_type="execute_script",
                message=f"[DRY-RUN] Would execute PowerShell script",
                data={
                    "script_content": script_content[:500] + "..." if len(script_content) > 500 else script_content,
                    "script_length": len(script_content),
                    "dry_run": True
                }
            )

        try:
            result = subprocess.run(
                self.powershell_cmd,
                input=script_content,
                capture_output=True,
                text=True,
                timeout=self.timeout
            )
            
            stdout = result.stdout.strip() if result.stdout else ""
            stderr = result.stderr.strip() if result.stderr else ""
            
            return ActionResult(
                success=result.returncode == 0,
                action_type="execute_script",
                message=f"PowerShell script executed with return code {result.returncode}",
                data={
                    "script_length": len(script_content),
                    "return_code": result.returncode,
                    "stdout": stdout,
                    "stderr": stderr,
                    "success": result.returncode == 0
                },
                error=stderr if result.returncode != 0 else None
            )
            
        except subprocess.TimeoutExpired:
            logger.error("PowerShell script timed out")
            return ActionResult(
                success=False,
                action_type="execute_script",
                message="PowerShell script timed out",
                error=f"Script exceeded timeout of {self.timeout} seconds"
            )
        except Exception as e:
            logger.error(f"Error executing PowerShell script: {e}")
            return ActionResult(
                success=False,
                action_type="execute_script",
                message="Failed to execute PowerShell script",
                error=str(e)
            )

    def get_system_info(self) -> ActionResult:
        """
        Get system information using PowerShell.

        Returns:
            ActionResult with system information or error
        """
        logger.info("Getting system information via PowerShell")
        
        command = """
        Get-ComputerInfo | Select-Object OsName, OsVersion, OsArchitecture, TotalPhysicalMemory, 
        CsProcessors, CsSystemType, WindowsRegisteredOwner, WindowsRegisteredOrganization
        """
        
        return self.execute_command(command)

    def get_running_processes(self) -> ActionResult:
        """
        Get list of running processes using PowerShell.

        Returns:
            ActionResult with process list or error
        """
        logger.info("Getting running processes via PowerShell")
        
        command = """
        Get-Process | Select-Object Name, Id, CPU, WorkingSet, StartTime | 
        Sort-Object CPU -Descending | Select-Object -First 50
        """
        
        return self.execute_command(command)

    def get_services(self, status: str = "running") -> ActionResult:
        """
        Get list of services using PowerShell.

        Args:
            status: Service status to filter (running, stopped, etc.)

        Returns:
            ActionResult with service list or error
        """
        logger.info(f"Getting {status} services via PowerShell")
        
        command = f"""
        Get-Service | Where-Object {{$_.Status -eq '{status}'}} | 
        Select-Object Name, DisplayName, Status, StartType | Sort-Object Name
        """
        
        return self.execute_command(command)

    def get_installed_programs(self) -> ActionResult:
        """
        Get list of installed programs using PowerShell.

        Returns:
            ActionResult with program list or error
        """
        logger.info("Getting installed programs via PowerShell")
        
        command = """
        Get-WmiObject -Class Win32_Product | Select-Object Name, Version, Vendor | Sort-Object Name
        """
        
        return self.execute_command(command)

    def check_file_hash(self, file_path: str, algorithm: str = "SHA256") -> ActionResult:
        """
        Calculate file hash using PowerShell.

        Args:
            file_path: Path to the file
            algorithm: Hash algorithm (MD5, SHA1, SHA256, SHA384, SHA512)

        Returns:
            ActionResult with file hash or error
        """
        logger.info(f"Calculating {algorithm} hash for {file_path}")
        
        command = f"""
        Get-FileHash -Path "{file_path}" -Algorithm {algorithm} | Select-Object Hash, Algorithm
        """
        
        return self.execute_command(command)