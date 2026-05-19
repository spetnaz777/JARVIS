import re
from enum import Enum
from dataclasses import dataclass
from typing import Optional
from loguru import logger


class RiskLevel(str, Enum):
    STANDARD = "STANDARD"
    ELEVATED = "ELEVATED"
    CRITICAL = "CRITICAL"


@dataclass
class SafetyResult:
    is_safe: bool
    risk_level: RiskLevel
    reason: Optional[str] = None
    requires_confirmation: bool = False


CRITICAL_PATTERNS = [
    # File deletion
    (r"\brm\s+-[rRfF]*\s", "Recursive/forced file deletion"),
    (r"\bdel\s+/[fFs]", "Forced file deletion"),
    (r"\bRemove-Item\b", "PowerShell file/folder removal"),
    (r"\brd\s+/[sS]", "Remove directory with contents"),
    (r"\brmdir\s+/[sS]", "Remove directory with contents"),
    (r"\bformat\s+[a-zA-Z]:", "Disk format command"),
    (r"\bdiskpart\b", "Disk partitioning tool"),

    # System shutdown/restart
    (r"\bshutdown\b", "System shutdown command"),
    (r"\brestart-computer\b", "System restart command"),
    (r"\bStop-Computer\b", "System stop command"),
    (r"\bRestart-Computer\b", "System restart command"),
    (r"\binit\s+[06]\b", "System halt/reboot"),

    # Registry modifications
    (r"\breg\s+(add|delete|import|export)\b", "Registry modification"),
    (r"\bSet-ItemProperty\s+.*HKLM", "Registry modification (HKLM)"),
    (r"\bNew-Item\s+.*HKCU", "Registry modification (HKCU)"),
    (r"\bRemove-Item\s+.*HK[LC]", "Registry key deletion"),
    (r"HKEY_LOCAL_MACHINE", "Registry access (Local Machine)"),
    (r"HKEY_CURRENT_USER.*delete", "Registry deletion (Current User)"),

    # Network/Firewall configuration
    (r"\bnetsh\s+firewall\b", "Firewall configuration"),
    (r"\bnetsh\s+advfirewall\b", "Advanced firewall configuration"),
    (r"\bSet-NetFirewallRule\b", "Firewall rule modification"),
    (r"\bNew-NetFirewallRule\b", "New firewall rule"),
    (r"\bDisable-NetAdapter\b", "Network adapter disable"),
    (r"\bipconfig\s+/release\b", "IP address release"),

    # Administrator/privilege escalation
    (r"\brunas\s+/user:administrator\b", "Run as administrator"),
    (r"\bStart-Process\s+.*-Verb\s+RunAs\b", "Elevated process execution"),
    (r"\bsudo\b", "Privilege escalation"),

    # Critical system processes
    (r"\bkill\s+.*\b(csrss|winlogon|lsass|services|svchost)\b", "Critical process termination"),
    (r"\bStop-Process\s+.*\b(csrss|winlogon|lsass|services)\b", "Critical service termination"),
    (r"\btaskkill\s+.*\b(csrss|winlogon|lsass)\b", "Critical process kill"),
]

ELEVATED_PATTERNS = [
    # Package installations
    (r"\bchoco\s+install\b", "Chocolatey package installation"),
    (r"\bwinget\s+install\b", "Windows package installation"),
    (r"\bpip\s+install\b", "Python package installation"),
    (r"\bnpm\s+install\s+-g\b", "Global npm package installation"),
    (r"\bscoop\s+install\b", "Scoop package installation"),
    (r"\bmsiexec\b", "MSI installer execution"),
    (r"\bSetup\.exe\b", "Setup executable"),
    (r"\binstall\.exe\b", "Installer execution"),

    # System configuration
    (r"\bsc\s+(create|delete|config)\b", "Windows service modification"),
    (r"\bschtasks\s+/create\b", "Scheduled task creation"),
    (r"\bschtasks\s+/delete\b", "Scheduled task deletion"),
    (r"\bSet-Service\b", "Service configuration change"),
    (r"\bNew-Service\b", "New service creation"),

    # Process termination (non-critical)
    (r"\btaskkill\b", "Process termination"),
    (r"\bStop-Process\b", "PowerShell process stop"),
    (r"\bkill\b", "Process kill signal"),

    # Account management
    (r"\bnet\s+user\b", "User account management"),
    (r"\bnet\s+localgroup\b", "Local group management"),
    (r"\bAdd-LocalUser\b", "New user creation"),
    (r"\bRemove-LocalUser\b", "User deletion"),

    # Environment modifications
    (r"\b\[System\.Environment\]::SetEnvironmentVariable\b", "System environment variable change"),
    (r"\bsetx\s+.*\/M\b", "System-wide environment variable"),
]

CRITICAL_PROCESS_BLACKLIST = {
    "csrss.exe", "winlogon.exe", "lsass.exe", "services.exe",
    "smss.exe", "wininit.exe", "System", "Registry",
}


class SafetyChecker:
    def __init__(self):
        self.critical_patterns = [(re.compile(p, re.IGNORECASE), reason) for p, reason in CRITICAL_PATTERNS]
        self.elevated_patterns = [(re.compile(p, re.IGNORECASE), reason) for p, reason in ELEVATED_PATTERNS]

    def check_command(self, command: str) -> SafetyResult:
        command_lower = command.lower().strip()

        for pattern, reason in self.critical_patterns:
            if pattern.search(command):
                logger.warning(f"CRITICAL risk command detected: {reason} | Command: {command[:100]}")
                return SafetyResult(
                    is_safe=False,
                    risk_level=RiskLevel.CRITICAL,
                    reason=f"Critical operation detected: {reason}",
                    requires_confirmation=True,
                )

        for pattern, reason in self.elevated_patterns:
            if pattern.search(command):
                logger.info(f"ELEVATED risk command detected: {reason} | Command: {command[:100]}")
                return SafetyResult(
                    is_safe=False,
                    risk_level=RiskLevel.ELEVATED,
                    reason=f"Elevated risk operation: {reason}",
                    requires_confirmation=True,
                )

        for proc in CRITICAL_PROCESS_BLACKLIST:
            if proc.lower() in command_lower:
                logger.warning(f"Critical process reference detected: {proc}")
                return SafetyResult(
                    is_safe=False,
                    risk_level=RiskLevel.CRITICAL,
                    reason=f"Reference to critical system process: {proc}",
                    requires_confirmation=True,
                )

        return SafetyResult(
            is_safe=True,
            risk_level=RiskLevel.STANDARD,
            requires_confirmation=False,
        )

    def get_risk_explanation(self, result: SafetyResult) -> str:
        if result.risk_level == RiskLevel.CRITICAL:
            return (
                f"⚠️ CRITICAL RISK: {result.reason}\n\n"
                "This command could cause irreversible damage to your system, "
                "delete important files, or compromise security. "
                "Proceed only if you are absolutely certain."
            )
        elif result.risk_level == RiskLevel.ELEVATED:
            return (
                f"⚡ ELEVATED RISK: {result.reason}\n\n"
                "This command will modify system settings, install software, "
                "or terminate processes. Review carefully before proceeding."
            )
        return "Command appears safe to execute."


safety_checker = SafetyChecker()
