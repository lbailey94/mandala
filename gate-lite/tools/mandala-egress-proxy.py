#!/usr/bin/env python3
"""mandala-egress-proxy — fail-closed allowlist egress over a Unix socket.

The sandbox runs with no network (`bwrap --unshare-all`); the only egress
channel is this proxy's AF_UNIX socket, bind-mounted into the sandbox. Every
connection is checked against an explicit host allowlist; everything else is
refused and recorded. The proxy runs on the host, so it performs name
resolution — the sandbox cannot resolve anything itself and has no raw
network to bypass the check.

Log (JSON Lines) records every decision for the receipt:

    {"ts": ..., "event": "connect"|"http"|"error", "host": str, "port": int,
     "allowed": bool, "bytes_out": int, "bytes_in": int, "reason": str}

`bytes_out` counts bytes sent to the destination (requests), `bytes_in`
counts bytes received from it (responses).

Usage:
    python3 mandala-egress-proxy.py --socket PATH --log PATH \
        --allow host[:port] [--allow ...] [--timeout 10]
"""

from __future__ import annotations

import argparse
import json
import os
import selectors
import socket
import socketserver
import sys
import threading
import time
import urllib.parse
from types import SimpleNamespace

MAX_HEAD = 65536
TUNNEL_BUF = 65536
HOP_HEADERS = {
    "proxy-connection", "connection", "keep-alive", "te", "trailer",
    "transfer-encoding", "upgrade", "proxy-authorization",
}


def _normalize_host(host: str) -> str:
    return host.strip().strip("[]").lower().rstrip(".")


class Allowlist:
    def __init__(self, entries):
        self.hosts = set()
        self.host_ports = set()
        for entry in entries:
            entry = entry.strip()
            if not entry:
                continue
            host, _, port = entry.rpartition(":")
            if host and port.isdigit():
                self.host_ports.add((_normalize_host(host), int(port)))
            elif host:
                self.hosts.add(_normalize_host(host))
            else:
                self.hosts.add(_normalize_host(entry))

    def allows(self, host: str, port: int) -> bool:
        host = _normalize_host(host)
        return host in self.hosts or (host, port) in self.host_ports


class ThreadingUnixServer(socketserver.ThreadingMixIn, socketserver.UnixStreamServer):
    daemon_threads = True
    allow_reuse_address = False


class Handler(socketserver.BaseRequestHandler):
    def handle(self):
        cfg = self.server.cfg
        try:
            self.request.settimeout(cfg.timeout)
            parsed = self._read_head()
            if parsed is None:
                return
            (method, target), headers, rest = parsed
            if method.upper() == "CONNECT":
                self._connect(target, cfg)
            else:
                self._http(method, target, headers, rest, cfg)
        except (OSError, ValueError) as exc:
            cfg.log({"event": "error", "allowed": False, "reason": str(exc)})
            self._reply(b"HTTP/1.1 502 Bad Gateway\r\nContent-Length: 0\r\n\r\n")
        finally:
            try:
                self.request.close()
            except OSError:
                pass

    def _read_head(self):
        data = b""
        while b"\r\n\r\n" not in data:
            chunk = self.request.recv(4096)
            if not chunk:
                return None
            data += chunk
            if len(data) > MAX_HEAD:
                raise ValueError("request head too large")
        head, _, rest = data.partition(b"\r\n\r\n")
        lines = head.decode("latin-1").split("\r\n")
        parts = lines[0].split()
        if len(parts) < 2:
            raise ValueError("malformed request line")
        headers = {}
        for line in lines[1:]:
            if ":" in line:
                name, value = line.split(":", 1)
                headers[name.strip().lower()] = value.strip()
        return (parts[0], parts[1]), headers, rest

    def _reply(self, payload: bytes):
        try:
            self.request.sendall(payload)
        except OSError:
            pass

    @staticmethod
    def _parse_authority(authority: str, default_port: int) -> tuple[str, int]:
        if authority.startswith("["):
            host, _, rest = authority[1:].partition("]")
            port = int(rest[1:]) if rest.startswith(":") and rest[1:] else default_port
            return host, port
        host, _, port = authority.rpartition(":")
        if host and port.isdigit():
            return host, int(port)
        return authority, default_port

    def _connect(self, authority: str, cfg):
        host, port = self._parse_authority(authority, 443)
        if not cfg.allow.allows(host, port):
            cfg.log({"event": "connect", "host": host, "port": port,
                     "allowed": False, "reason": "not-in-allowlist"})
            self._reply(b"HTTP/1.1 403 Forbidden\r\nContent-Length: 0\r\n\r\n")
            return
        try:
            upstream = socket.create_connection((host, port), timeout=cfg.timeout)
        except OSError as exc:
            cfg.log({"event": "connect", "host": host, "port": port,
                     "allowed": False, "reason": f"upstream-error: {exc}"})
            self._reply(b"HTTP/1.1 502 Bad Gateway\r\nContent-Length: 0\r\n\r\n")
            return
        self._reply(b"HTTP/1.1 200 Connection Established\r\n\r\n")
        bytes_out, bytes_in = self._relay(upstream, cfg)
        upstream.close()
        cfg.log({"event": "connect", "host": host, "port": port, "allowed": True,
                 "bytes_out": bytes_out, "bytes_in": bytes_in})

    def _relay(self, upstream, cfg) -> tuple[int, int]:
        upstream.settimeout(None)
        self.request.settimeout(None)
        client = self.request
        bytes_out = bytes_in = 0
        selector = selectors.DefaultSelector()
        selector.register(client, selectors.EVENT_READ, "client")
        selector.register(upstream, selectors.EVENT_READ, "upstream")
        try:
            while True:
                for key, _ in selector.select(timeout=cfg.timeout * 6):
                    source = key.fileobj
                    destination = upstream if key.data == "client" else client
                    try:
                        data = source.recv(TUNNEL_BUF)
                    except OSError:
                        data = b""
                    if not data:
                        return bytes_out, bytes_in
                    destination.sendall(data)
                    if key.data == "client":
                        bytes_out += len(data)
                    else:
                        bytes_in += len(data)
        finally:
            selector.close()

    def _http(self, method: str, target: str, headers: dict, rest: bytes, cfg):
        if target.startswith("http://"):
            split = urllib.parse.urlsplit(target)
            host = split.hostname or ""
            port = split.port or 80
            path = split.path or "/"
            if split.query:
                path += "?" + split.query
        else:
            host_header = headers.get("host", "")
            host, port = self._parse_authority(host_header, 80)
            path = target
        if not host:
            cfg.log({"event": "http", "allowed": False, "reason": "no-host"})
            self._reply(b"HTTP/1.1 400 Bad Request\r\nContent-Length: 0\r\n\r\n")
            return
        if not cfg.allow.allows(host, port):
            cfg.log({"event": "http", "host": host, "port": port,
                     "allowed": False, "reason": "not-in-allowlist"})
            self._reply(b"HTTP/1.1 403 Forbidden\r\nContent-Length: 0\r\n\r\n")
            return
        body = rest
        length = int(headers.get("content-length") or 0)
        if length > 0:
            while len(body) < length:
                chunk = self.request.recv(min(65536, length - len(body)))
                if not chunk:
                    break
                body += chunk
        request = [f"{method} {path} HTTP/1.1"]
        for name, value in headers.items():
            if name not in HOP_HEADERS and name != "host":
                request.append(f"{name}: {value}")
        request.append(f"Host: {host}")
        request.append("Connection: close")
        payload = ("\r\n".join(request) + "\r\n\r\n").encode("latin-1") + body
        try:
            upstream = socket.create_connection((host, port), timeout=cfg.timeout)
            upstream.sendall(payload)
            bytes_out = len(payload)
            bytes_in = 0
            while True:
                data = upstream.recv(TUNNEL_BUF)
                if not data:
                    break
                self.request.sendall(data)
                bytes_in += len(data)
            upstream.close()
        except OSError as exc:
            cfg.log({"event": "http", "host": host, "port": port,
                     "allowed": False, "reason": f"upstream-error: {exc}"})
            self._reply(b"HTTP/1.1 502 Bad Gateway\r\nContent-Length: 0\r\n\r\n")
            return
        cfg.log({"event": "http", "host": host, "port": port, "allowed": True,
                 "bytes_out": bytes_out, "bytes_in": bytes_in})


def main():
    parser = argparse.ArgumentParser(
        description="Fail-closed allowlist egress proxy over a Unix socket."
    )
    parser.add_argument("--socket", required=True)
    parser.add_argument("--log", required=True)
    parser.add_argument("--allow", action="append", default=[],
                        help="allowed host or host:port (repeatable)")
    parser.add_argument("--timeout", type=int, default=10)
    args = parser.parse_args()

    allowlist = Allowlist(args.allow)
    log_lock = threading.Lock()
    log_file = open(args.log, "a", buffering=1, encoding="utf-8")

    def log(entry: dict):
        record = {"ts": time.time(), **entry}
        with log_lock:
            log_file.write(json.dumps(record, sort_keys=True) + "\n")

    if os.path.exists(args.socket):
        os.unlink(args.socket)
    server = ThreadingUnixServer(args.socket, Handler)
    os.chmod(args.socket, 0o666)
    server.cfg = SimpleNamespace(allow=allowlist, log=log, timeout=args.timeout)
    print(f"mandala-egress-proxy listening on {args.socket} "
          f"({len(allowlist.hosts) + len(allowlist.host_ports)} allowlist entries)",
          file=sys.stderr, flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
        log_file.close()
        try:
            os.unlink(args.socket)
        except OSError:
            pass


if __name__ == "__main__":
    main()
