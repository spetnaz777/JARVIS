import subprocess
import asyncio
import os
import shlex
from typing import Optional
from dataclasses import dataclass
from loguru import logger

from config import config
from safety_checker import safety_checker, SafetyResult, RiskLevel


@dataclass
class CommandResult:
    success: bool
    stdout: str
    stderr: str
    return_code: int
    command: str
    blocked: bool = False
    safety_result: Optional[SafetyResult] = None


class CommandExecutor:
    def __init__(self):
        self.working_dir = os.path.expanduser("~")

    async def execute(self, command: str, bypass_safety: bool = False) -> CommandResult:
        command = command.strip()
        if not command:
            return CommandResult(success=False, stdout="", stderr="Empty command", return_code=1, command=command)

        safety_result = safety_checker.check_command(command)

        if not bypass_safety and safety_result.requires_confirmation:
            logger.info(f"Command blocked pending confirmation: {command[:100]}")
            return CommandResult(
                success=False,
                stdout="",
                stderr=safety_checker.get_risk_explanation(safety_result),
                return_code=-1,
                command=command,
                blocked=True,
                safety_result=safety_result,
            )

        return await self._run_command(command, safety_result)

    async def _run_command(self, command: str, safety_result: SafetyResult) -> CommandResult:
        try:
            loop = asyncio.get_event_loop()
            result = await loop.run_in_executor(
                None, self._execute_sync, command
            )
            return result
        except asyncio.TimeoutError:
            logger.error(f"Command timed out: {command[:100]}")
            return CommandResult(
                success=False,
                stdout="",
                stderr=f"Command timed out after {config.COMMAND_TIMEOUT} seconds",
                return_code=-1,
                command=command,
                safety_result=safety_result,
            )
        except Exception as e:
            logger.error(f"Command execution error: {e}")
            return CommandResult(
                success=False,
                stdout="",
                stderr=str(e),
                return_code=-1,
                command=command,
                safety_result=safety_result,
            )

    def _execute_sync(self, command: str) -> CommandResult:
        try:
            proc = subprocess.run(
                ["powershell.exe", "-NoProfile", "-NonInteractive", "-Command", command],
                capture_output=True,
                text=True,
                timeout=config.COMMAND_TIMEOUT,
                cwd=self.working_dir,
                creationflags=subprocess.CREATE_NO_WINDOW,
            )
            success = proc.returncode == 0
            stdout = proc.stdout.strip()
            stderr = proc.stderr.strip()
            logger.info(f"Command executed (rc={proc.returncode}): {command[:80]}")
            return CommandResult(
                success=success,
                stdout=stdout,
                stderr=stderr,
                return_code=proc.returncode,
                command=command,
            )
        except subprocess.TimeoutExpired:
            raise asyncio.TimeoutError()
        except Exception as e:
            logger.error(f"Subprocess error: {e}")
            return CommandResult(
                success=False,
                stdout="",
                stderr=str(e),
                return_code=-1,
                command=command,
            )

    def set_working_dir(self, path: str):
        if os.path.isdir(path):
            self.working_dir = path
            logger.info(f"Working directory set to: {path}")


command_executor = CommandExecutor()
