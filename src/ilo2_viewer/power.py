"""IPMI power control for iLO2 devices.

Uses pyghmi in a subprocess to avoid event loop conflicts with asyncio.
"""

from __future__ import annotations

import json
import subprocess
import sys


def _run_ipmi(host: str, user: str, password: str, action: str) -> str:
    """Run IPMI command in a subprocess to avoid asyncio conflicts."""
    script = f"""
import json
from pyghmi.ipmi import command
try:
    cmd = command.Command(bmc={host!r}, userid={user!r}, password={password!r})
    if {action!r} == "status":
        result = cmd.get_power()
        print(json.dumps({{"result": result.get("powerstate", "unknown")}}))
    else:
        result = cmd.set_power({action!r})
        # Re-query status after action
        import time; time.sleep(1)
        status = cmd.get_power()
        print(json.dumps({{"result": status.get("powerstate", "unknown")}}))
    cmd.ipmi_session.logout()
except Exception as e:
    print(json.dumps({{"error": str(e)}}))
"""
    proc = subprocess.run(
        [sys.executable, "-c", script],
        capture_output=True, text=True, timeout=15,
    )
    if proc.returncode != 0:
        stderr = proc.stderr.strip()
        return json.dumps({"error": stderr or "IPMI command failed"})
    return proc.stdout.strip() or json.dumps({"error": "no response"})


def set_power(host: str, user: str, password: str, action: str) -> str:
    """Execute a power action via IPMI. Returns result string."""
    if action not in ("status", "on", "off", "reset", "shutdown"):
        return f"unknown action: {action}"

    raw = _run_ipmi(host, user, password, action)
    try:
        data = json.loads(raw)
        if "error" in data:
            raise RuntimeError(data["error"])
        return data["result"]
    except json.JSONDecodeError:
        raise RuntimeError(f"bad IPMI response: {raw}")
