"""Device checks. Each check is fast (<~2 s), read-only, and returns a CheckResult.

All checks run in parallel from run_all(); one failing check never breaks the report.
"""
from __future__ import annotations

import os
import socket
import sys
import tempfile
import time
from concurrent.futures import ThreadPoolExecutor

import psutil

from . import demo
from .models import CheckResult

GB = 1024 ** 3
MB = 1024 ** 2


# ---------------------------------------------------------------- disk + temp
def _dir_size(path: str, budget_s: float = 1.5) -> int:
    total, deadline = 0, time.monotonic() + budget_s
    for root, _dirs, files in os.walk(path, onerror=lambda e: None):
        for f in files:
            try:
                total += os.path.getsize(os.path.join(root, f))
            except OSError:
                pass
        if time.monotonic() > deadline:
            break
    return total


def check_disk() -> CheckResult:
    root = os.environ.get("SystemDrive", "C:") + "\\" if sys.platform == "win32" else "/"
    u = psutil.disk_usage(root)
    temp_bytes = _dir_size(tempfile.gettempdir())
    pct = u.percent
    free_gb = u.free / GB

    if demo.has("disk"):
        pct, free_gb, temp_bytes = 93.4, 7.8, int(4.2 * GB)

    temp_gb = temp_bytes / GB
    metric = {"used_pct": round(pct, 1), "free_gb": round(free_gb, 1), "temp_gb": round(temp_gb, 2)}
    if pct >= 90:
        return CheckResult("disk", "Disk space", "crit",
                           f"Disk is {pct:.0f}% full ({free_gb:.1f} GB free). {temp_gb:.1f} GB is temporary junk.",
                           metric, fix_id="clean_temp", minutes_per_week=6)
    if pct >= 80 or temp_gb >= 2:
        return CheckResult("disk", "Disk space", "warn",
                           f"Disk is {pct:.0f}% full; {temp_gb:.1f} GB of temp files can go.",
                           metric, fix_id="clean_temp", minutes_per_week=3)
    return CheckResult("disk", "Disk space", "ok", f"{free_gb:.0f} GB free.", metric)


# ---------------------------------------------------------------- uptime
def check_uptime() -> CheckResult:
    days = (time.time() - psutil.boot_time()) / 86400
    if demo.has("uptime"):
        days = 13.6
    metric = {"days": round(days, 1)}
    if days >= 7:
        return CheckResult("uptime", "Restart", "warn",
                           f"Not restarted for {days:.0f} days - updates and memory leaks pile up.",
                           metric, fix_id="schedule_restart", minutes_per_week=10)
    return CheckResult("uptime", "Restart", "ok", f"Restarted {days:.1f} days ago.", metric)


# ---------------------------------------------------------------- cpu / ram hogs
IGNORED_PROCS = {"system idle process", "system", "idle", "registry", "memory compression"}


def check_cpu_hogs() -> CheckResult:
    procs = [p for p in psutil.process_iter(["name", "pid"])]
    for p in procs:
        try:
            p.cpu_percent(None)
        except psutil.Error:
            pass
    time.sleep(1.0)
    ncpu = psutil.cpu_count() or 1
    samples = []
    for p in procs:
        try:
            name = (p.info["name"] or "").lower()
            if name in IGNORED_PROCS or p.pid == os.getpid():
                continue
            samples.append((p.cpu_percent(None) / ncpu, p.info["name"], p.pid))
        except psutil.Error:
            pass
    samples.sort(reverse=True)
    mem = psutil.virtual_memory().percent

    if demo.has("cpu_hog"):
        samples = [(34.0, "OneDriveSetup.exe", -1)] + samples

    top = samples[0] if samples else (0.0, "-", -1)
    metric = {"top_process": top[1], "top_cpu_pct": round(top[0], 1), "ram_pct": mem}
    if top[0] >= 25:
        return CheckResult("cpu_hog", "Background load", "warn",
                           f"{top[1]} is using {top[0]:.0f}% CPU in the background.",
                           metric, fix_id="kill_process", fix_args={"pid": top[2], "name": top[1]},
                           minutes_per_week=8)
    if mem >= 90:
        return CheckResult("cpu_hog", "Background load", "warn",
                           f"Memory is {mem:.0f}% used - apps will start swapping.",
                           metric, minutes_per_week=5)
    return CheckResult("cpu_hog", "Background load", "ok", "Nothing heavy running in the background.", metric)


# ---------------------------------------------------------------- network
WORK_HOSTS = ["teams.microsoft.com", "outlook.office.com", "www.google.com"]


def _probe(host: str) -> tuple[float | None, float | None]:
    """Returns (dns_ms, tcp_ms) or None on failure."""
    t0 = time.perf_counter()
    try:
        addr = socket.getaddrinfo(host, 443, proto=socket.IPPROTO_TCP)[0][4]
    except OSError:
        return None, None
    dns_ms = (time.perf_counter() - t0) * 1000
    t1 = time.perf_counter()
    try:
        with socket.create_connection(addr[:2], timeout=2):
            pass
    except OSError:
        return dns_ms, None
    return dns_ms, (time.perf_counter() - t1) * 1000


def check_network() -> CheckResult:
    with ThreadPoolExecutor(len(WORK_HOSTS)) as ex:
        res = dict(zip(WORK_HOSTS, ex.map(_probe, WORK_HOSTS)))
    dns = [d for d, _ in res.values() if d is not None]
    tcp = [t for _, t in res.values() if t is not None]
    dns_ms = max(dns) if dns else None
    tcp_ms = sum(tcp) / len(tcp) if tcp else None

    if demo.has("dns"):
        dns_ms, tcp_ms = 1850.0, 96.0

    metric = {"dns_ms": dns_ms and round(dns_ms), "latency_ms": tcp_ms and round(tcp_ms),
              "reachable": len(tcp), "probed": len(WORK_HOSTS)}
    if not tcp:
        return CheckResult("dns", "Network", "crit", "Can't reach Teams or Outlook. Check Wi-Fi / VPN.",
                           metric, fix_id="flush_dns", minutes_per_week=30)
    if dns_ms and dns_ms > 500:
        return CheckResult("dns", "Network", "warn",
                           f"Name lookups take {dns_ms/1000:.1f}s - every Teams/Outlook load feels slow.",
                           metric, fix_id="flush_dns", minutes_per_week=7)
    return CheckResult("dns", "Network", "ok",
                       f"Teams & Outlook reachable ({tcp_ms:.0f} ms).", metric)


# ---------------------------------------------------------------- battery
def check_battery() -> CheckResult:
    b = psutil.sensors_battery()
    if b is None:
        return CheckResult("battery", "Battery", "ok", "Desktop - no battery.", {})
    metric = {"percent": b.percent, "plugged": b.power_plugged}
    if b.percent < 20 and not b.power_plugged:
        return CheckResult("battery", "Battery", "warn",
                           f"Battery at {b.percent:.0f}% and unplugged - charge before your first meeting.",
                           metric, minutes_per_week=2)
    return CheckResult("battery", "Battery", "ok", f"Battery {b.percent:.0f}%.", metric)


# ---------------------------------------------------------------- pending reboot / startup apps (Windows)
def check_updates() -> CheckResult:
    pending = False
    startup_count = 0
    if sys.platform == "win32":
        import winreg
        for key in (r"SOFTWARE\Microsoft\Windows\CurrentVersion\WindowsUpdate\Auto Update\RebootRequired",
                    r"SOFTWARE\Microsoft\Windows\CurrentVersion\Component Based Servicing\RebootPending"):
            try:
                winreg.CloseKey(winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, key))
                pending = True
            except OSError:
                pass
        for hive in (winreg.HKEY_CURRENT_USER, winreg.HKEY_LOCAL_MACHINE):
            try:
                with winreg.OpenKey(hive, r"Software\Microsoft\Windows\CurrentVersion\Run") as k:
                    startup_count += winreg.QueryInfoKey(k)[1]
            except OSError:
                pass
    metric = {"reboot_pending": pending, "startup_apps": startup_count}
    if pending:
        return CheckResult("updates", "Updates", "warn",
                           "An update is waiting for a restart - it will force one at a bad moment.",
                           metric, fix_id="schedule_restart", minutes_per_week=5)
    if startup_count > 12:
        return CheckResult("updates", "Updates", "warn",
                           f"{startup_count} apps launch at startup - boot is slower than it needs to be.",
                           metric, minutes_per_week=4)
    return CheckResult("updates", "Updates", "ok", "Up to date, startup is lean.", metric)


ALL_CHECKS = [check_disk, check_uptime, check_cpu_hogs, check_network, check_battery, check_updates]


def run_all() -> list[CheckResult]:
    def safe(fn):
        try:
            return fn()
        except Exception as e:  # a broken check must not break the morning card
            return CheckResult(fn.__name__.removeprefix("check_"), fn.__name__, "ok",
                               f"Check skipped ({type(e).__name__}).", {})
    with ThreadPoolExecutor(len(ALL_CHECKS)) as ex:
        return list(ex.map(safe, ALL_CHECKS))
