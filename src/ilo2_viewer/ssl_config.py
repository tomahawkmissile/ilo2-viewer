"""SSL/TLS configuration for connecting to legacy iLO2 devices.

iLO2 firmware uses TLSv1.0 with legacy renegotiation and self-signed certificates.
OpenSSL 3.0+ blocks both TLSv1.0 and unsafe legacy renegotiation by default.
We use pyOpenSSL to gain low-level control over the SSL context flags.
"""

from __future__ import annotations

import select
import socket
import warnings

import requests
import urllib3
from requests.adapters import HTTPAdapter
from urllib3.poolmanager import PoolManager
from urllib3.util.ssl_ import create_urllib3_context

from OpenSSL import SSL, crypto

SSL_OP_LEGACY_SERVER_CONNECT = 0x4


class _PyOpenSSLContext:
    """Wraps a pyOpenSSL SSL.Context to be usable by urllib3."""

    def __init__(self):
        self._ctx = SSL.Context(SSL.TLSv1_METHOD)
        self._ctx.set_options(SSL_OP_LEGACY_SERVER_CONNECT)
        self._ctx.set_cipher_list(b"ALL:@SECLEVEL=0")
        self._ctx.set_verify(SSL.VERIFY_NONE, lambda *a: True)

    @property
    def openssl_context(self):
        return self._ctx


class _LegacyTLSAdapter(HTTPAdapter):
    """HTTPS adapter that uses pyOpenSSL with TLSv1.0 and legacy renegotiation."""

    def init_poolmanager(self, connections, maxsize, block=False, **kwargs):
        ctx = _PyOpenSSLContext()
        kwargs["ssl_context"] = ctx.openssl_context
        # We need to inject our pyOpenSSL context. urllib3 with pyOpenSSL
        # support (via urllib3.contrib.pyopenssl) can do this, but it's
        # simpler to just use the standard ssl adapter path with a patched context.
        # Fall through to custom pool manager.
        self.poolmanager = _LegacyPoolManager(
            num_pools=connections, maxsize=maxsize, block=block
        )


class _LegacyPoolManager(PoolManager):
    """Pool manager that injects our pyOpenSSL context into connections."""

    def _new_pool(self, scheme, host, port, request_context=None):
        if scheme == "https":
            if request_context is None:
                request_context = {}
            ctx = create_urllib3_context()
            ctx.check_hostname = False
            ctx.verify_mode = 0  # CERT_NONE
            # These flags may not fully work on OpenSSL 3.0, but we set them anyway.
            # The actual fix is the pyOpenSSL-based session (see ILO2Session).
            request_context["ssl_context"] = ctx
        return super()._new_pool(scheme, host, port, request_context)


def create_session() -> requests.Session:
    """Create a requests session for iLO2. Uses HTTP by default since
    HTTPS with TLSv1.0 requires special handling via pyOpenSSL."""
    warnings.filterwarnings("ignore", category=urllib3.exceptions.InsecureRequestWarning)
    session = requests.Session()
    session.verify = False
    session.headers.update({
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; WOW64; Trident/7.0; rv:11.0) like Gecko",
        "Accept-Language": "de-DE",
    })
    return session


def https_get(hostname: str, path: str, headers: dict[str, str] | None = None) -> str:
    """Perform an HTTPS GET using pyOpenSSL with TLSv1.0 + legacy renegotiation.

    Returns the full HTTP response (headers + decoded body) as a string.
    This bypasses requests/urllib3 entirely since they cannot be made to
    work with OpenSSL 3.0's TLSv1.0 restrictions.
    """
    ctx = SSL.Context(SSL.TLSv1_METHOD)
    ctx.set_options(SSL_OP_LEGACY_SERVER_CONNECT)
    ctx.set_cipher_list(b"ALL:@SECLEVEL=0")
    ctx.set_verify(SSL.VERIFY_NONE, lambda *a: True)

    sock = socket.create_connection((hostname, 443), timeout=15)
    conn = SSL.Connection(ctx, sock)
    conn.set_connect_state()

    # Non-blocking handshake
    while True:
        try:
            conn.do_handshake()
            break
        except SSL.WantReadError:
            select.select([sock], [], [], 10)

    # Build request
    hdrs = {
        "Host": hostname,
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; WOW64; Trident/7.0; rv:11.0) like Gecko",
        "Accept-Language": "de-DE",
        "Connection": "close",
    }
    if headers:
        hdrs.update(headers)

    header_lines = "\r\n".join(f"{k}: {v}" for k, v in hdrs.items())
    request = f"GET {path} HTTP/1.1\r\n{header_lines}\r\n\r\n"
    conn.sendall(request.encode("latin-1"))

    # Read full response
    data = b""
    headers_done = False
    is_chunked = False
    content_length = -1

    while True:
        try:
            r, _, _ = select.select([sock], [], [], 5)
            if not r:
                break
            chunk = conn.recv(8192)
            if not chunk:
                break
            data += chunk

            # Check if we have complete headers
            if not headers_done and b"\r\n\r\n" in data:
                headers_done = True
                header_part = data[:data.index(b"\r\n\r\n")].decode("latin-1").lower()
                is_chunked = "transfer-encoding: chunked" in header_part
                for line in header_part.split("\r\n"):
                    if line.startswith("content-length:"):
                        content_length = int(line.split(":", 1)[1].strip())

            # Detect end of response
            if headers_done:
                if is_chunked and b"\r\n0\r\n" in data:
                    break
                elif content_length >= 0:
                    body_start = data.index(b"\r\n\r\n") + 4
                    if len(data) - body_start >= content_length:
                        break

        except SSL.WantReadError:
            continue
        except (SSL.ZeroReturnError, SSL.SysCallError):
            break

    conn.close()
    sock.close()

    # Parse HTTP response: split headers from body
    raw = data.decode("latin-1")
    if "\r\n\r\n" in raw:
        resp_headers, body = raw.split("\r\n\r\n", 1)
    else:
        return raw

    # Handle chunked transfer encoding
    if "transfer-encoding: chunked" in resp_headers.lower():
        body = _decode_chunked(body)

    # Return headers + body so callers can parse Set-Cookie etc.
    return resp_headers + "\r\n\r\n" + body


def _decode_chunked(data: str) -> str:
    """Decode HTTP chunked transfer encoding."""
    result: list[str] = []
    pos = 0
    while pos < len(data):
        # Find chunk size line
        end = data.find("\r\n", pos)
        if end == -1:
            break
        size_str = data[pos:end].strip()
        if not size_str:
            pos = end + 2
            continue
        try:
            chunk_size = int(size_str, 16)
        except ValueError:
            break
        if chunk_size == 0:
            break
        start = end + 2
        result.append(data[start:start + chunk_size])
        pos = start + chunk_size + 2  # skip trailing \r\n
    return "".join(result)
