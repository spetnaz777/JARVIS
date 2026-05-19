import subprocess
import psutil
import time
from dataclasses import dataclass
from loguru import logger


@dataclass
class SystemStatus:
    cpu_percent: float
    memory_percent: float
    memory_used_gb: float
    memory_total_gb: float
    disk_percent: float
    disk_used_gb: float
    disk_total_gb: float
    cpu_freq_ghz: float
    process_count: int
    uptime_hours: float

    def to_dict(self) -> dict:
        return {
            "cpu": {
                "percent": round(self.cpu_percent, 1),
                "freq_ghz": round(self.cpu_freq_ghz, 2),
            },
            "memory": {
                "percent": round(self.memory_percent, 1),
                "used_gb": round(self.memory_used_gb, 2),
                "total_gb": round(self.memory_total_gb, 2),
            },
            "disk": {
                "percent": round(self.disk_percent, 1),
                "used_gb": round(self.disk_used_gb, 2),
                "total_gb": round(self.disk_total_gb, 2),
            },
            "processes": self.process_count,
            "uptime_hours": round(self.uptime_hours, 1),
        }


class SystemController:
    def get_status(self) -> SystemStatus:
        cpu = psutil.cpu_percent(interval=0.5)
        mem = psutil.virtual_memory()
        disk = psutil.disk_usage("C:\\")
        freq = psutil.cpu_freq()
        uptime = time.time() - psutil.boot_time()

        return SystemStatus(
            cpu_percent=cpu,
            memory_percent=mem.percent,
            memory_used_gb=mem.used / (1024 ** 3),
            memory_total_gb=mem.total / (1024 ** 3),
            disk_percent=disk.percent,
            disk_used_gb=disk.used / (1024 ** 3),
            disk_total_gb=disk.total / (1024 ** 3),
            cpu_freq_ghz=freq.current / 1000 if freq else 0.0,
            process_count=len(psutil.pids()),
            uptime_hours=uptime / 3600,
        )

    def set_volume(self, level: int) -> bool:
        level = max(0, min(100, level))
        try:
            script = f"""
$wshShell = New-Object -ComObject wscript.shell
$wshShell.SendKeys([char]173)
Add-Type -TypeDefinition @'
using System.Runtime.InteropServices;
[Guid("5CDF2C82-841E-4546-9722-0CF74078229A"), InterfaceType(ComInterfaceType.InterfaceIsIUnknown)]
interface IAudioEndpointVolume {{
    int f(); int g(); int h(); int i();
    int SetMasterVolumeLevelScalar(float fLevel, System.Guid pguidEventContext);
    int j();
    int GetMasterVolumeLevelScalar(out float pfLevel);
}}
[Guid("BCDE0395-E52F-467C-8E3D-C4579291692E")]
class MMDeviceEnumerator {{}}
'@
"""
            ps_simple = f"""
$volume = {level}
$wshShell = New-Object -ComObject wscript.shell
[audio]::Volume = $volume / 100
"""
            subprocess.run(
                ["powershell.exe", "-NoProfile", "-Command",
                 f"(New-Object -com Shell.Application).Windows() | Out-Null; "
                 f"$vol = New-Object -ComObject WScript.Shell; "
                 f"1..50 | ForEach-Object {{ $vol.SendKeys([char]174) }}; "
                 f"$steps = [Math]::Round({level} / 2); "
                 f"1..$steps | ForEach-Object {{ $vol.SendKeys([char]175) }}"],
                capture_output=True,
                timeout=10,
            )
            logger.info(f"Volume set to {level}%")
            return True
        except Exception as e:
            logger.error(f"Volume control error: {e}")
            return False

    def get_top_processes(self, n: int = 10) -> list[dict]:
        processes = []
        for proc in psutil.process_iter(["pid", "name", "cpu_percent", "memory_percent"]):
            try:
                info = proc.info
                processes.append({
                    "pid": info["pid"],
                    "name": info["name"],
                    "cpu": round(info["cpu_percent"] or 0, 1),
                    "memory": round(info["memory_percent"] or 0, 1),
                })
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                continue

        processes.sort(key=lambda p: p["cpu"], reverse=True)
        return processes[:n]

    def get_network_info(self) -> dict:
        try:
            net = psutil.net_io_counters()
            addrs = psutil.net_if_addrs()
            return {
                "bytes_sent_mb": round(net.bytes_sent / (1024 ** 2), 2),
                "bytes_recv_mb": round(net.bytes_recv / (1024 ** 2), 2),
                "interfaces": list(addrs.keys())[:5],
            }
        except Exception as e:
            logger.error(f"Network info error: {e}")
            return {}


system_controller = SystemController()
