#!/usr/bin/env python3
"""mandala-fetch — fetch a URL through the sandbox egress proxy.

The sandbox has no raw network. This helper connects to the allowlist proxy's
Unix socket (bind-mounted by the wrapper), issues a CONNECT for the URL's
host, optionally wraps the tunnel in TLS, and performs one GET. It resolves
nothing itself: the proxy performs name resolution and enforces the allowlist.

Exit codes:
    0  2xx response received (body written to stdout or --out)
    22 non-2xx response received (status printed to stderr)
    1  transport failure or proxy refusal
    2  usage/setup error (missing socket, bad URL)

Usage:
    mandala-fetch URL [--out PATH] [--sock PATH] [--max-bytes N]
"""

from __future__ import annotations

import argparse
import os
import socket
import ssl
import sys
import urllib.parse

MAX_HEAD = 65536
MAX_BYTES_DEFAULT = 8 * 1024 * 1024


def read_head(sock: socket.socket) -> tuple[int, bytes]:
    data = b""
    while b"\r\n\r\n" not in data:
        chunk = sock.recv(4096)
        if not chunk:
            raise OSError("connection closed while reading response head")
        data += chunk
        if len(data) > MAX_HEAD:
            raise OSError("response head too large")
    head, _, rest = data.partition(b"\r\n\r\n")
    line = head.split(b"\r\n", 1)[0].decode("latin-1")
    parts = line.split()
    if len(parts) < 2 or not parts[1].isdigit():
        raise OSError(f"malformed status line: {line!r}")
    return int(parts[1]), rest


def main() -> int:
    parser = argparse.ArgumentParser(description="Fetch through the sandbox egress proxy.")
    parser.add_argument("url")
    parser.add_argument("--sock", default=os.environ.get("MANDALA_EGRESS_SOCK", ""))
    parser.add_argument("--out", default="-")
    parser.add_argument("--max-bytes", type=int, default=MAX_BYTES_DEFAULT)
    args = parser.parse_args()

    if not args.sock:
        print("mandala-fetch: no egress socket (MANDALA_EGRESS_SOCK unset)", file=sys.stderr)
        return 2
    if not os.path.exists(args.sock):
        print(f"mandala-fetch: egress socket not found: {args.sock}", file=sys.stderr)
        return 1

    split = urllib.parse.urlsplit(args.url)
    if split.scheme not in ("http", "https") or not split.hostname:
        print(f"mandala-fetch: unsupported URL: {args.url}", file=sys.stderr)
        return 2
    host = split.hostname
    port = split.port or (443 if split.scheme == "https" else 80)
    path = split.path or "/"
    if split.query:
        path += "?" + split.query

    try:
        sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        sock.settimeout(30)
        sock.connect(args.sock)
        sock.sendall(f"CONNECT {host}:{port} HTTP/1.1\r\nHost: {host}:{port}\r\n\r\n".encode())
        status, _ = read_head(sock)
        if status != 200:
            print(f"mandala-fetch: proxy refused CONNECT (status {status})", file=sys.stderr)
            sock.close()
            return 1
        if split.scheme == "https":
            context = ssl.create_default_context()
            sock = context.wrap_socket(sock, server_hostname=host)
        request = (f"GET {path} HTTP/1.1\r\nHost: {host}\r\n"
                   f"User-Agent: mandala-fetch/1\r\nConnection: close\r\n\r\n")
        sock.sendall(request.encode("latin-1"))
        status, body = read_head(sock)
        chunks = [body]
        total = len(body)
        while total < args.max_bytes:
            chunk = sock.recv(65536)
            if not chunk:
                break
            chunks.append(chunk)
            total += len(chunk)
        sock.close()
    except (OSError, ssl.SSLError) as exc:
        print(f"mandala-fetch: transport failure: {exc}", file=sys.stderr)
        return 1

    payload = b"".join(chunks)
    print(f"mandala-fetch: status={status} bytes={len(payload)}", file=sys.stderr)
    if args.out == "-":
        sys.stdout.buffer.write(payload)
    else:
        with open(args.out, "wb") as handle:
            handle.write(payload)
    return 0 if 200 <= status < 300 else 22


if __name__ == "__main__":
    sys.exit(main())
