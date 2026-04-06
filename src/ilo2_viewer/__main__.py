"""Entry point for the iLO2 Remote Console Viewer.

Usage:
    python -m ilo2_viewer <hostname> <username> <password>
    python -m ilo2_viewer -c <config.ini>
    python -m ilo2_viewer   (uses config.ini in current directory)
"""

from __future__ import annotations

import argparse
import asyncio
import configparser
import sys

from .auth import authenticate
from .web_server import WebConsole


def main():
    parser = argparse.ArgumentParser(
        description="HP iLO2 Remote Console Viewer",
        usage="%(prog)s [hostname username password | -c config.ini]",
    )
    parser.add_argument("hostname", nargs="?", help="iLO2 hostname or IP")
    parser.add_argument("username", nargs="?", help="Login username")
    parser.add_argument("password", nargs="?", help="Login password")
    parser.add_argument("-c", "--config", help="Path to config.ini file")
    parser.add_argument("-p", "--port", type=int, default=8080,
                        help="Web server port (default: 8080)")

    args = parser.parse_args()

    hostname = args.hostname
    username = args.username
    password = args.password

    if args.config:
        cfg = configparser.ConfigParser()
        cfg.read(args.config)
        hostname = cfg.get("ilo2", "hostname")
        username = cfg.get("ilo2", "username")
        password = cfg.get("ilo2", "password")
    elif not hostname:
        cfg = configparser.ConfigParser()
        if cfg.read("config.ini"):
            hostname = cfg.get("ilo2", "hostname")
            username = cfg.get("ilo2", "username")
            password = cfg.get("ilo2", "password")
        else:
            parser.print_help()
            sys.exit(1)

    if not all([hostname, username, password]):
        parser.error("hostname, username, and password are required")

    try:
        params = authenticate(hostname, username, password)
    except Exception as e:
        print(f"Authentication failed: {e}")
        sys.exit(1)

    console = WebConsole(hostname, params, username=username, password=password)
    try:
        asyncio.run(console.run(port=args.port))
    except KeyboardInterrupt:
        console.shutdown()


if __name__ == "__main__":
    main()
