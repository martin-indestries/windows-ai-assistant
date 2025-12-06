"""
Windows Registry system action module.

Provides Windows registry operations using winreg while enforcing
dry-run semantics and safety checks.
"""

import logging
from typing import Any, List, Optional, Union

try:
    import winreg
    WINREG_AVAILABLE = True
except ImportError:
    WINREG_AVAILABLE = False

from jarvis.action_executor import ActionResult

logger = logging.getLogger(__name__)


# Registry key constants
HKEY_CLASSES_ROOT = "HKEY_CLASSES_ROOT"
HKEY_CURRENT_USER = "HKEY_CURRENT_USER"
HKEY_LOCAL_MACHINE = "HKEY_LOCAL_MACHINE"
HKEY_USERS = "HKEY_USERS"
HKEY_CURRENT_CONFIG = "HKEY_CURRENT_CONFIG"

# Registry value type constants
REG_SZ = "REG_SZ"
REG_EXPAND_SZ = "REG_EXPAND_SZ"
REG_BINARY = "REG_BINARY"
REG_DWORD = "REG_DWORD"
REG_DWORD_LITTLE_ENDIAN = "REG_DWORD_LITTLE_ENDIAN"
REG_DWORD_BIG_ENDIAN = "REG_DWORD_BIG_ENDIAN"
REG_LINK = "REG_LINK"
REG_MULTI_SZ = "REG_MULTI_SZ"
REG_RESOURCE_LIST = "REG_RESOURCE_LIST"
REG_FULL_RESOURCE_DESCRIPTOR = "REG_FULL_RESOURCE_DESCRIPTOR"
REG_RESOURCE_REQUIREMENTS_LIST = "REG_RESOURCE_REQUIREMENTS_LIST"
REG_QWORD = "REG_QWORD"


class RegistryActions:
    """
    Windows Registry system actions.

    Wraps winreg operations with dry-run support and safety checks.
    Only available on Windows.
    """

    def __init__(self, dry_run: bool = False) -> None:
        """
        Initialize registry actions.

        Args:
            dry_run: If True, preview actions without executing
        """
        self.dry_run = dry_run
        self._key_map = {
            HKEY_CLASSES_ROOT: winreg.HKEY_CLASSES_ROOT if WINREG_AVAILABLE else None,
            HKEY_CURRENT_USER: winreg.HKEY_CURRENT_USER if WINREG_AVAILABLE else None,
            HKEY_LOCAL_MACHINE: winreg.HKEY_LOCAL_MACHINE if WINREG_AVAILABLE else None,
            HKEY_USERS: winreg.HKEY_USERS if WINREG_AVAILABLE else None,
            HKEY_CURRENT_CONFIG: winreg.HKEY_CURRENT_CONFIG if WINREG_AVAILABLE else None,
        }
        logger.info("RegistryActions initialized")

    def _get_winreg_key(self, root_key: str):
        """Convert string key name to winreg constant."""
        if not WINREG_AVAILABLE:
            return None
        return self._key_map.get(root_key)

    def _value_type_to_string(self, value_type: int) -> str:
        """Convert winreg value type to string representation."""
        type_map = {
            winreg.REG_SZ: REG_SZ,
            winreg.REG_EXPAND_SZ: REG_EXPAND_SZ,
            winreg.REG_BINARY: REG_BINARY,
            winreg.REG_DWORD: REG_DWORD,
            winreg.REG_DWORD_LITTLE_ENDIAN: REG_DWORD_LITTLE_ENDIAN,
            winreg.REG_DWORD_BIG_ENDIAN: REG_DWORD_BIG_ENDIAN,
            winreg.REG_LINK: REG_LINK,
            winreg.REG_MULTI_SZ: REG_MULTI_SZ,
            winreg.REG_RESOURCE_LIST: REG_RESOURCE_LIST,
            winreg.REG_FULL_RESOURCE_DESCRIPTOR: REG_FULL_RESOURCE_DESCRIPTOR,
            winreg.REG_RESOURCE_REQUIREMENTS_LIST: REG_RESOURCE_REQUIREMENTS_LIST,
            winreg.REG_QWORD: REG_QWORD,
        }
        return type_map.get(value_type, f"UNKNOWN_{value_type}")

    def list_subkeys(self, root_key: str, subkey_path: str = "") -> ActionResult:
        """
        List subkeys under a registry key.

        Args:
            root_key: Root key name (e.g., HKEY_CURRENT_USER)
            subkey_path: Path to subkey (empty string for root)

        Returns:
            ActionResult with list of subkeys or error
        """
        logger.info(f"Listing subkeys: {root_key}\\{subkey_path}")
        
        if not WINREG_AVAILABLE:
            return ActionResult(
                success=False,
                action_type="list_subkeys",
                message="Windows Registry operations not available on this platform",
                error="winreg module only available on Windows"
            )

        winreg_root = self._get_winreg_key(root_key)
        if winreg_root is None:
            return ActionResult(
                success=False,
                action_type="list_subkeys",
                message=f"Invalid root key: {root_key}",
                error="Root key not recognized"
            )

        if self.dry_run:
            return ActionResult(
                success=True,
                action_type="list_subkeys",
                message=f"[DRY-RUN] Would list subkeys under {root_key}\\{subkey_path}",
                data={"root_key": root_key, "subkey_path": subkey_path, "dry_run": True}
            )

        try:
            with winreg.OpenKey(winreg_root, subkey_path, 0, winreg.KEY_READ) as key:
                subkeys = []
                i = 0
                while True:
                    try:
                        subkey_name = winreg.EnumKey(key, i)
                        subkeys.append(subkey_name)
                        i += 1
                    except WindowsError:
                        break

                return ActionResult(
                    success=True,
                    action_type="list_subkeys",
                    message=f"Found {len(subkeys)} subkeys",
                    data={"subkeys": subkeys, "root_key": root_key, "subkey_path": subkey_path}
                )
        except WindowsError as e:
            logger.error(f"Error listing subkeys: {e}")
            return ActionResult(
                success=False,
                action_type="list_subkeys",
                message="Failed to list subkeys",
                error=str(e)
            )
        except Exception as e:
            logger.error(f"Unexpected error listing subkeys: {e}")
            return ActionResult(
                success=False,
                action_type="list_subkeys",
                message="Failed to list subkeys",
                error=str(e)
            )

    def list_values(self, root_key: str, subkey_path: str = "") -> ActionResult:
        """
        List values under a registry key.

        Args:
            root_key: Root key name (e.g., HKEY_CURRENT_USER)
            subkey_path: Path to subkey (empty string for root)

        Returns:
            ActionResult with list of values or error
        """
        logger.info(f"Listing values: {root_key}\\{subkey_path}")
        
        if not WINREG_AVAILABLE:
            return ActionResult(
                success=False,
                action_type="list_values",
                message="Windows Registry operations not available on this platform",
                error="winreg module only available on Windows"
            )

        winreg_root = self._get_winreg_key(root_key)
        if winreg_root is None:
            return ActionResult(
                success=False,
                action_type="list_values",
                message=f"Invalid root key: {root_key}",
                error="Root key not recognized"
            )

        if self.dry_run:
            return ActionResult(
                success=True,
                action_type="list_values",
                message=f"[DRY-RUN] Would list values under {root_key}\\{subkey_path}",
                data={"root_key": root_key, "subkey_path": subkey_path, "dry_run": True}
            )

        try:
            with winreg.OpenKey(winreg_root, subkey_path, 0, winreg.KEY_READ) as key:
                values = []
                i = 0
                while True:
                    try:
                        name, value, value_type = winreg.EnumValue(key, i)
                        values.append({
                            "name": name,
                            "value": value,
                            "type": self._value_type_to_string(value_type)
                        })
                        i += 1
                    except WindowsError:
                        break

                return ActionResult(
                    success=True,
                    action_type="list_values",
                    message=f"Found {len(values)} values",
                    data={"values": values, "root_key": root_key, "subkey_path": subkey_path}
                )
        except WindowsError as e:
            logger.error(f"Error listing values: {e}")
            return ActionResult(
                success=False,
                action_type="list_values",
                message="Failed to list values",
                error=str(e)
            )
        except Exception as e:
            logger.error(f"Unexpected error listing values: {e}")
            return ActionResult(
                success=False,
                action_type="list_values",
                message="Failed to list values",
                error=str(e)
            )

    def read_value(self, root_key: str, subkey_path: str, value_name: str) -> ActionResult:
        """
        Read a specific registry value.

        Args:
            root_key: Root key name (e.g., HKEY_CURRENT_USER)
            subkey_path: Path to subkey
            value_name: Name of the value to read

        Returns:
            ActionResult with value data or error
        """
        logger.info(f"Reading value: {root_key}\\{subkey_path}\\{value_name}")
        
        if not WINREG_AVAILABLE:
            return ActionResult(
                success=False,
                action_type="read_value",
                message="Windows Registry operations not available on this platform",
                error="winreg module only available on Windows"
            )

        winreg_root = self._get_winreg_key(root_key)
        if winreg_root is None:
            return ActionResult(
                success=False,
                action_type="read_value",
                message=f"Invalid root key: {root_key}",
                error="Root key not recognized"
            )

        if self.dry_run:
            return ActionResult(
                success=True,
                action_type="read_value",
                message=f"[DRY-RUN] Would read value {root_key}\\{subkey_path}\\{value_name}",
                data={"root_key": root_key, "subkey_path": subkey_path, "value_name": value_name, "dry_run": True}
            )

        try:
            with winreg.OpenKey(winreg_root, subkey_path, 0, winreg.KEY_READ) as key:
                value, value_type = winreg.QueryValueEx(key, value_name)
                return ActionResult(
                    success=True,
                    action_type="read_value",
                    message=f"Read value {value_name}",
                    data={
                        "value": value,
                        "type": self._value_type_to_string(value_type),
                        "root_key": root_key,
                        "subkey_path": subkey_path,
                        "value_name": value_name
                    }
                )
        except WindowsError as e:
            logger.error(f"Error reading value: {e}")
            return ActionResult(
                success=False,
                action_type="read_value",
                message="Failed to read value",
                error=str(e)
            )
        except Exception as e:
            logger.error(f"Unexpected error reading value: {e}")
            return ActionResult(
                success=False,
                action_type="read_value",
                message="Failed to read value",
                error=str(e)
            )

    def write_value(
        self,
        root_key: str,
        subkey_path: str,
        value_name: str,
        value: Any,
        value_type: str = REG_SZ
    ) -> ActionResult:
        """
        Write a registry value.

        Args:
            root_key: Root key name (e.g., HKEY_CURRENT_USER)
            subkey_path: Path to subkey
            value_name: Name of the value to write
            value: Value data
            value_type: Value type (e.g., REG_SZ, REG_DWORD)

        Returns:
            ActionResult indicating success or failure
        """
        logger.info(f"Writing value: {root_key}\\{subkey_path}\\{value_name} = {repr(value)}")
        
        if not WINREG_AVAILABLE:
            return ActionResult(
                success=False,
                action_type="write_value",
                message="Windows Registry operations not available on this platform",
                error="winreg module only available on Windows"
            )

        winreg_root = self._get_winreg_key(root_key)
        if winreg_root is None:
            return ActionResult(
                success=False,
                action_type="write_value",
                message=f"Invalid root key: {root_key}",
                error="Root key not recognized"
            )

        # Convert string type to winreg constant
        type_map = {
            REG_SZ: winreg.REG_SZ,
            REG_EXPAND_SZ: winreg.REG_EXPAND_SZ,
            REG_BINARY: winreg.REG_BINARY,
            REG_DWORD: winreg.REG_DWORD,
            REG_MULTI_SZ: winreg.REG_MULTI_SZ,
            REG_QWORD: winreg.REG_QWORD,
        }
        winreg_type = type_map.get(value_type, winreg.REG_SZ)

        if self.dry_run:
            return ActionResult(
                success=True,
                action_type="write_value",
                message=f"[DRY-RUN] Would write value {root_key}\\{subkey_path}\\{value_name} = {repr(value)}",
                data={
                    "root_key": root_key,
                    "subkey_path": subkey_path,
                    "value_name": value_name,
                    "value": value,
                    "value_type": value_type,
                    "dry_run": True
                }
            )

        try:
            with winreg.CreateKey(winreg_root, subkey_path) as key:
                winreg.SetValueEx(key, value_name, 0, winreg_type, value)
                return ActionResult(
                    success=True,
                    action_type="write_value",
                    message=f"Wrote value {value_name}",
                    data={
                        "root_key": root_key,
                        "subkey_path": subkey_path,
                        "value_name": value_name,
                        "value": value,
                        "value_type": value_type
                    }
                )
        except WindowsError as e:
            logger.error(f"Error writing value: {e}")
            return ActionResult(
                success=False,
                action_type="write_value",
                message="Failed to write value",
                error=str(e)
            )
        except Exception as e:
            logger.error(f"Unexpected error writing value: {e}")
            return ActionResult(
                success=False,
                action_type="write_value",
                message="Failed to write value",
                error=str(e)
            )

    def delete_value(self, root_key: str, subkey_path: str, value_name: str) -> ActionResult:
        """
        Delete a registry value.

        Args:
            root_key: Root key name (e.g., HKEY_CURRENT_USER)
            subkey_path: Path to subkey
            value_name: Name of the value to delete

        Returns:
            ActionResult indicating success or failure
        """
        logger.info(f"Deleting value: {root_key}\\{subkey_path}\\{value_name}")
        
        if not WINREG_AVAILABLE:
            return ActionResult(
                success=False,
                action_type="delete_value",
                message="Windows Registry operations not available on this platform",
                error="winreg module only available on Windows"
            )

        winreg_root = self._get_winreg_key(root_key)
        if winreg_root is None:
            return ActionResult(
                success=False,
                action_type="delete_value",
                message=f"Invalid root key: {root_key}",
                error="Root key not recognized"
            )

        if self.dry_run:
            return ActionResult(
                success=True,
                action_type="delete_value",
                message=f"[DRY-RUN] Would delete value {root_key}\\{subkey_path}\\{value_name}",
                data={"root_key": root_key, "subkey_path": subkey_path, "value_name": value_name, "dry_run": True}
            )

        try:
            with winreg.OpenKey(winreg_root, subkey_path, 0, winreg.KEY_SET_VALUE) as key:
                winreg.DeleteValue(key, value_name)
                return ActionResult(
                    success=True,
                    action_type="delete_value",
                    message=f"Deleted value {value_name}",
                    data={"root_key": root_key, "subkey_path": subkey_path, "value_name": value_name}
                )
        except WindowsError as e:
            logger.error(f"Error deleting value: {e}")
            return ActionResult(
                success=False,
                action_type="delete_value",
                message="Failed to delete value",
                error=str(e)
            )
        except Exception as e:
            logger.error(f"Unexpected error deleting value: {e}")
            return ActionResult(
                success=False,
                action_type="delete_value",
                message="Failed to delete value",
                error=str(e)
            )