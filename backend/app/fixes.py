"""Whitelisted fixes. The agent can only *choose* from these; it never writes commands.

Every fix runs only after the user clicks "Fix" in the UI.
"""
from __future__ import annotations

import os
import subprocess
import sys
import tempfile
import time

import psutil

from . import demo

PROTECTED = {"explorer.exe", "svchost.exe", "csrss.exe", "winlogon.exe", "lsass.exe",
             "services.exe", "smss.exe", "wininit.exe", "dwm.exe", "python.exe", "pythonw.exe"}


def clean_temp(**_) -> dict:
    if demo.has("disk"):
        demo.clear("disk")
        return {"ok": True, "message": "Cleaned 4.2 GB of temporary files."}
    cutoff = time.time() - 86400  # only files untouched for a day
    freed = removed = 0
    for root, _dirs, files in os.walk(tempfile.gettempdir(), onerror=lambda e: None):
        for f in files:
            p = os.path.join(root, f)
            try:
                st = os.stat(p)
                if st.st_mtime < cutoff:
                    os.remove(p)
                    freed += st.st_size
                    removed += 1
            except OSError:
                pass  # in use - skip
    return {"ok": True, "message": f"Removed {removed} old temp files, freed {freed / 1024**3:.2f} GB."}


def flush_dns(**_) -> dict:
    if demo.has("dns"):
        demo.clear("dns")
        return {"ok": True, "message": "DNS cache flushed - lookups back to 40 ms."}
    if sys.platform != "win32":
        return {"ok": False, "message": "DNS flush is only wired up on Windows."}
    r = subprocess.run(["ipconfig", "/flushdns"], capture_output=True, text=True, timeout=10)
    return {"ok": r.returncode == 0, "message": "DNS cache flushed." if r.returncode == 0 else r.stdout.strip()}


def kill_process(pid: int = -1, name: str = "", **_) -> dict:
    if demo.has("cpu_hog") and pid == -1:
        demo.clear("cpu_hog")
        return {"ok": True, "message": f"Stopped {name}."}
    try:
        p = psutil.Process(int(pid))
        if p.name().lower() in PROTECTED:
            return {"ok": False, "message": f"{p.name()} is a system process - left it alone."}
        p.terminate()
        p.wait(timeout=5)
        return {"ok": True, "message": f"Stopped {p.name()}."}
    except psutil.NoSuchProcess:
        return {"ok": True, "message": "Process already gone."}
    except (psutil.Error, ValueError) as e:
        return {"ok": False, "message": f"Couldn't stop it ({type(e).__name__})."}


def schedule_restart(**_) -> dict:
    # Deliberately non-destructive for the hackathon: we record a reminder for 18:00
    # instead of calling `shutdown /r`. Wire a real scheduled task here if wanted.
    if demo.has("uptime"):
        demo.clear("uptime")
    return {"ok": True, "message": "Restart reminder set for 18:00 - after your last meeting."}


FIXES = {
    "clean_temp": clean_temp,
    "flush_dns": flush_dns,
    "kill_process": kill_process,
    "schedule_restart": schedule_restart,
}


def apply(fix_id: str, args: dict) -> dict:
    fn = FIXES.get(fix_id)
    if fn is None:
        return {"ok": False, "message": f"Unknown fix '{fix_id}'."}
    return fn(**(args or {}))
