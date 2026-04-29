"""iLO2 authentication flow.

Ported from Main.java - implements the 3-stage login to retrieve
DVC session parameters. Uses pyOpenSSL for HTTPS to handle iLO2's
TLSv1.0 + legacy renegotiation requirements on OpenSSL 3.0+.
"""

from __future__ import annotations

import base64
import re
import time
from pathlib import Path

from . import ssl_config

COOKIE_FILE = Path("data.cook")

# iLO2 throttles repeated logins. Retry stage1 a few times when we hit it.
_LOGIN_DELAY_MAX_RETRIES = 6
_LOGIN_DELAY_FALLBACK_SECONDS = 10


def _extract(html: str, prefix: str, suffix: str) -> str:
    try:
        start = html.index(prefix) + len(prefix)
        end = html.index(suffix, start)
    except ValueError:
        raise ValueError(f"could not find {prefix!r}…{suffix!r} in response")
    return html[start:end]


def _login_delay_seconds(html: str) -> int | None:
    """If iLO2 returned a Login Delay page, return seconds to wait, else None."""
    if "Login Delay" not in html:
        return None
    # iLO2's delay page usually contains something like "Login Delay : 10 seconds"
    m = re.search(r"Login Delay[^0-9]{0,40}(\d+)", html)
    if m:
        return int(m.group(1))
    return _LOGIN_DELAY_FALLBACK_SECONDS


def _get(hostname: str, path: str, extra_headers: dict[str, str] | None = None) -> str:
    """GET a page from the iLO2 over HTTPS (via pyOpenSSL)."""
    return ssl_config.https_get(hostname, path, headers=extra_headers)


def stage1(hostname: str) -> tuple[str, str]:
    """GET login.htm and extract sessionkey + sessionindex.

    iLO2 throttles repeat logins with a "Login Delay" page that omits the
    JS session vars. Detect that and wait it out instead of bubbling up
    a confusing "substring not found" ValueError.
    """
    last_html = ""
    for attempt in range(_LOGIN_DELAY_MAX_RETRIES):
        html = _get(hostname, "/login.htm", {"Cookie": "hp-iLO-Login="})
        last_html = html

        delay = _login_delay_seconds(html)
        if delay is not None:
            wait = min(delay + 1, 60)
            print(f"iLO2 login throttled, waiting {wait}s (attempt {attempt + 1}/{_LOGIN_DELAY_MAX_RETRIES})")
            time.sleep(wait)
            continue

        try:
            session_key = _extract(html, 'var sessionkey="', '";')
            session_index = _extract(html, 'var sessionindex="', '";')
        except ValueError:
            # Not a delay page but still missing the vars — short retry then fail loudly.
            time.sleep(2)
            continue
        return session_key, session_index

    snippet = last_html[:200].replace("\n", " ")
    raise RuntimeError(
        f"iLO2 login.htm did not return session vars after {_LOGIN_DELAY_MAX_RETRIES} attempts. "
        f"Response began with: {snippet!r}"
    )


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

    return params


def is_valid(hostname: str, cookie: str) -> bool:
    """Check if an existing session cookie is still valid."""
    html = _get(hostname, "/ie_index.htm", {"Cookie": cookie})
    return "Login Delay" not in html and "Integrated Lights-Out 2 Login" not in html


def authenticate(hostname: str, username: str, password: str, **kwargs) -> dict[str, str]:
    """Full authentication flow, returns DVC params dict."""
    supercookie = ""

    if COOKIE_FILE.exists():
        saved = COOKIE_FILE.read_text().strip()
        try:
            reusable = bool(saved) and is_valid(hostname, saved)
        except Exception:
            reusable = False
        if reusable:
            supercookie = saved

    if not supercookie:
        session_key, session_index = stage1(hostname)
        supercookie = stage2(hostname, username, password, session_key, session_index)

    if not supercookie:
        raise RuntimeError(
            "iLO2 did not issue a session cookie — check username/password "
            "(case-sensitive) and that the account is not locked."
        )

    return stage3(hostname, supercookie)
