"""iLO2 authentication flow.

Ported from Main.java - implements the 3-stage login to retrieve
DVC session parameters. Uses pyOpenSSL for HTTPS to handle iLO2's
TLSv1.0 + legacy renegotiation requirements on OpenSSL 3.0+.
"""

from __future__ import annotations

import base64
import re
from pathlib import Path

from . import ssl_config

COOKIE_FILE = Path("data.cook")


def _extract(html: str, prefix: str, suffix: str) -> str:
    start = html.index(prefix) + len(prefix)
    end = html.index(suffix, start)
    return html[start:end]


def _get(hostname: str, path: str, extra_headers: dict[str, str] | None = None) -> str:
    """GET a page from the iLO2 over HTTPS (via pyOpenSSL)."""
    return ssl_config.https_get(hostname, path, headers=extra_headers)


def stage1(hostname: str) -> tuple[str, str]:
    """GET login.htm and extract sessionkey + sessionindex."""
    html = _get(hostname, "/login.htm", {"Cookie": "hp-iLO-Login="})

    session_key = _extract(html, 'var sessionkey="', '";')
    session_index = _extract(html, 'var sessionindex="', '";')
    print(f"Session key: {session_key}")
    print(f"Session  ID: {session_index}")
    return session_key, session_index


def stage2(
    hostname: str,
    username: str,
    password: str,
    session_key: str,
    session_index: str,
) -> str:
    """Send credentials to index.htm, return the session cookie."""
    user_b64 = base64.b64encode(username.encode()).decode()
    pass_b64 = base64.b64encode(password.encode()).decode()

    cookie_val = f"hp-iLO-Login={session_index}:{user_b64}:{pass_b64}:{session_key}"

    response = _get(hostname, "/index.htm", {"Cookie": cookie_val})

    # Extract Set-Cookie header from raw response
    supercookie = ""
    for match in re.finditer(r"Set-Cookie:\s*(hp-iLO-Session=[^\s;]+)", response, re.IGNORECASE):
        supercookie = match.group(1)

    if supercookie:
        COOKIE_FILE.write_text(supercookie)
        print(f"Session cookie: {supercookie}")
    else:
        # Show headers for debugging
        if "\r\n\r\n" in response:
            hdrs = response[:response.index("\r\n\r\n")]
            print(f"Stage2 response headers:\n{hdrs}", flush=True)
        else:
            print(f"Stage2: no Set-Cookie found", flush=True)

    return supercookie


def stage3(hostname: str, supercookie: str) -> dict[str, str]:
    """GET drc2fram.htm and extract DVC configuration parameters."""
    headers = {}
    if supercookie:
        headers["Cookie"] = supercookie

    html = _get(hostname, "/drc2fram.htm?restart=1", headers)

    params: dict[str, str] = {}

    # Parameters with quotes: info0="...";
    for key in ["info0", "info1", "info3", "info6", "info8",
                "infoa", "infob", "infoc", "infod", "infoo"]:
        try:
            params[key.upper()] = _extract(html, f'{key}="', '";')
        except ValueError:
            pass

    # Parameters without quotes: info7=...;
    for key in ["info7", "infom", "infomm", "infon"]:
        try:
            params[key.upper()] = _extract(html, f"{key}=", ";")
        except ValueError:
            pass

    # CABBASE
    try:
        params["CABBASE"] = _extract(html, "<PARAM NAME=CABBASE VALUE=", '>"')
    except ValueError:
        pass

    print(f"CABBASE = {params.get('CABBASE', 'N/A')}")
    return params


def is_valid(hostname: str, cookie: str) -> bool:
    """Check if an existing session cookie is still valid."""
    html = _get(hostname, "/ie_index.htm", {"Cookie": cookie})
    return "Login Delay" not in html and "Integrated Lights-Out 2 Login" not in html


def authenticate(hostname: str, username: str, password: str, **kwargs) -> dict[str, str]:
    """Full authentication flow, returns DVC params dict."""
    supercookie = ""

    # Try loading saved cookie
    if COOKIE_FILE.exists():
        print("Found datastore")
        saved = COOKIE_FILE.read_text().strip()
        print("Validating saved session...")
        if saved and is_valid(hostname, saved):
            print("Session valid, reusing cookie")
            supercookie = saved
        else:
            print("Datastore not valid, requesting Cookie")
            session_key, session_index = stage1(hostname)
            supercookie = stage2(hostname, username, password, session_key, session_index)
    else:
        print("Couldn't find datastore, requesting Cookie")
        session_key, session_index = stage1(hostname)
        supercookie = stage2(hostname, username, password, session_key, session_index)

    return stage3(hostname, supercookie)
