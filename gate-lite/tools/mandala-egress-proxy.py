#!/usr/bin/env python3
"""mandala-egress-proxy — fail-closed allowlist egress over a Unix socket.

The sandbox runs with no network (`bwrap --unshare-all`); the only egress
channel is this proxy's AF_UNIX socket, bind-mounted into the sandbox. Every
connection is checked against an explicit host allowlist; everything else is
refused and recorded. The proxy runs on the host, so it performs name
resolution — the sandbox cannot resolve anything itself and has no raw
network to bypass the check.

Log (JSON Lines) records every decision for the receipt:

    {"ts": ..., "event": "connect"|"http", "host": str, "port": int,
     "allowed": false, "reason": str}
    {"ts": ..., "event": "connect_start"|"http_start", "connection_id": str,
     "host": str, "port": int, "allowed": true}
    {"ts": ..., "event": "connect_complete"|"http_complete",
     "connection_id": str, "host": str, "port": int, "allowed": true,
     "bytes_out": int, "bytes_in": int}

Each allowed start must have one matching completion. A cut-off proxy run is
therefore distinguishable from an unused destination in the signed evidence.

`bytes_out` counts bytes sent to the destination (requests), `bytes_in`
counts bytes received from it (responses).

Usage:
    python3 mandala-egress-proxy.py --socket PATH --log PATH \
        --allow host[:port] [--allow ...] [--timeout 10]
"""

from __future__ import annotations

import argparse
import ipaddress
import json
import os
import re
import selectors
import signal
import socket
import socketserver
import sys
import threading
import time
import uuid
import urllib.parse
from types import SimpleNamespace

MAX_HEAD = 65536
MAX_BODY = 8 * 1024 * 1024
TUNNEL_BUF = 65536
MAX_CONNECTIONS = 64
HOP_HEADERS = {
    "proxy-connection", "connection", "keep-alive", "te", "trailer",
    "transfer-encoding", "upgrade", "proxy-authorization",
}


def _normalize_host(host: str) -> str:
    host = host.strip().strip("[]").lower().rstrip(".")
    try:
        return ipaddress.ip_address(host).compressed.lower()
    except ValueError:
        try:
            host = host.encode("idna").decode("ascii")
        except UnicodeError as exc:
            raise ValueError("invalid destination hostname") from exc
        if (not host or len(host) > 253
                or any(not re.fullmatch(r"[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?", label)
                       for label in host.split("."))):
            raise ValueError("invalid destination hostname")
        return host


class Allowlist:
    def __init__(self, entries):
        self.hosts = set()
        self.host_ports = set()
        self._pinned = {}
        self._resolve_lock = threading.Lock()
        for entry in entries:
            entry = entry.strip()
            if not entry:
                raise ValueError("empty allowlist entry")
            if entry.startswith("["):
                host, marker, rest = entry[1:].partition("]")
                if not marker or (rest and not rest.startswith(":")):
                    raise ValueError(f"invalid allowlist entry: {entry!r}")
                if rest == ":":
                    raise ValueError(f"invalid allowlist port: {entry!r}")
                try:
                    if ipaddress.ip_address(host).version != 6:
                        raise ValueError
                except ValueError as exc:
                    raise ValueError(f"invalid bracketed IPv6 allowlist host: {entry!r}") from exc
                port_text = rest[1:] if rest else ""
            else:
                try:
                    if ipaddress.ip_address(entry).version == 6:
                        self.hosts.add(_normalize_host(entry))
                        continue
                except ValueError:
                    pass
                host, marker, port_text = entry.rpartition(":")
                if not marker:
                    host, port_text = entry, ""
                elif not port_text:
                    raise ValueError(f"invalid allowlist port: {entry!r}")
            if not host or any(ch.isspace() for ch in host) or any(ch in host for ch in "/?#@"):
                raise ValueError(f"invalid allowlist host: {entry!r}")
            normalized = _normalize_host(host)
            if not normalized:
                raise ValueError(f"invalid allowlist host: {entry!r}")
            if port_text:
                if not port_text.isdigit() or not 1 <= int(port_text) <= 65535:
                    raise ValueError(f"invalid allowlist port: {entry!r}")
                self.host_ports.add((normalized, int(port_text)))
            elif ":" in host and not entry.startswith("["):
                # A bare IPv6 literal is a host-only entry; bracketed IPv6
                # with a port is required to make the port unambiguous.
                self.hosts.add(normalized)
            else:
                self.hosts.add(normalized)

    def allows(self, host: str, port: int) -> bool:
        host = _normalize_host(host)
        return host in self.hosts or (host, port) in self.host_ports

    def pinned_addresses(self, host: str, port: int):
        """Freeze each name on first use for this proxy invocation.

        DNS names may resolve only to global unicast destinations. Non-global
        destinations require the exact IP literal in the invocation allowlist;
        declaring a hostname never grants access to local/private addresses.
        """
        host = _normalize_host(host)
        if not self.allows(host, port):
            raise ValueError("destination not in allowlist")
        try:
            return (ipaddress.ip_address(host),)
        except ValueError:
            pass
        with self._resolve_lock:
            if host not in self._pinned:
                addresses = set()
                for family, _kind, _proto, _canon, sockaddr in socket.getaddrinfo(
                        host, None, type=socket.SOCK_STREAM):
                    if family not in (socket.AF_INET, socket.AF_INET6):
                        continue
                    address = ipaddress.ip_address(sockaddr[0])
                    effective = address.ipv4_mapped if isinstance(address, ipaddress.IPv6Address) else None
                    if not (effective or address).is_global or address.is_multicast:
                        raise ValueError("DNS destination is not global unicast; declare an exact IP literal")
                    addresses.add(address)
                if not addresses:
                    raise ValueError("DNS returned no usable destination addresses")
                self._pinned[host] = tuple(sorted(addresses, key=lambda address: (address.version, int(address))))
            return self._pinned[host]

    def connect(self, host: str, port: int, timeout: float):
        # Connect only to numeric addresses from the frozen set, never re-open
        # by hostname after the authority check (DNS rebinding/TOCTOU).
        last_error = None
        for address in self.pinned_addresses(host, port):
            family = socket.AF_INET6 if address.version == 6 else socket.AF_INET
            upstream = socket.socket(family, socket.SOCK_STREAM)
            upstream.settimeout(timeout)
            try:
                upstream.connect((str(address), port))
                return upstream
            except OSError as error:
                last_error = error
                upstream.close()
        raise last_error or OSError("no pinned destination connected")


class ThreadingUnixServer(socketserver.ThreadingMixIn, socketserver.UnixStreamServer):
    daemon_threads = False
    block_on_close = True
    allow_reuse_address = False
    max_connections = MAX_CONNECTIONS

    def __init__(self, *args, **kwargs):
        self._connection_slots = threading.BoundedSemaphore(self.max_connections)
        super().__init__(*args, **kwargs)

    def process_request(self, request, client_address):
        if not self._connection_slots.acquire(blocking=False):
            self.shutdown_request(request)
            return
        try:
            super().process_request(request, client_address)
        except Exception:
            self._connection_slots.release()
            raise

    def process_request_thread(self, request, client_address):
        try:
            super().process_request_thread(request, client_address)
        finally:
            self._connection_slots.release()


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
        if len(parts) != 3 or parts[2] not in ("HTTP/1.0", "HTTP/1.1"):
            raise ValueError("malformed request line")
        headers = {}
        for line in lines[1:]:
            if not line or ":" not in line:
                raise ValueError("malformed header")
            name, value = line.split(":", 1)
            name = name.strip().lower()
            if not name or any(ch not in "abcdefghijklmnopqrstuvwxyz0123456789!#$%&'*+-.^_`|~" for ch in name):
                raise ValueError("invalid header name")
            if name in headers:
                raise ValueError("duplicate request header")
            value = value.strip()
            if any(ord(ch) < 0x20 and ch != "\t" for ch in value):
                raise ValueError("invalid header value")
            headers[name] = value
        return (parts[0], parts[1]), headers, rest

    def _reply(self, payload: bytes):
        try:
            self.request.sendall(payload)
        except OSError:
            pass

    @staticmethod
    def _parse_authority(authority: str, default_port: int) -> tuple[str, int]:
        if (not authority or any(ch.isspace() for ch in authority)
                or any(ord(ch) < 0x20 for ch in authority)
                or authority.endswith(":")):
            raise ValueError("invalid destination authority")
        try:
            split = urllib.parse.urlsplit("//" + authority)
            if (not split.hostname or split.username is not None or split.password is not None
                    or split.path or split.query or split.fragment):
                raise ValueError("invalid destination authority")
            host = split.hostname
            port = default_port if split.port is None else split.port
        except ValueError as exc:
            raise ValueError("invalid destination authority") from exc
        if not 1 <= port <= 65535:
            raise ValueError("destination port out of range")
        return host, port

    def _connect(self, authority: str, cfg):
        host, port = self._parse_authority(authority, 443)
        if not cfg.allow.allows(host, port):
            cfg.log({"event": "connect", "host": host, "port": port,
                     "allowed": False, "reason": "not-in-allowlist"})
            self._reply(b"HTTP/1.1 403 Forbidden\r\nContent-Length: 0\r\n\r\n")
            return
        if not self._check_address_policy(host, port, cfg, "connect"):
            return
        connection_id = uuid.uuid4().hex
        cfg.log({"event": "connect_start", "connection_id": connection_id,
                 "host": host, "port": port, "allowed": True})
        try:
            upstream = cfg.allow.connect(host, port, cfg.timeout)
        except (OSError, ValueError) as exc:
            cfg.log({"event": "connect_complete", "connection_id": connection_id,
                     "host": host, "port": port, "allowed": True,
                     "bytes_out": 0, "bytes_in": 0,
                     "reason": f"upstream-error: {exc}"})
            self._reply(b"HTTP/1.1 502 Bad Gateway\r\nContent-Length: 0\r\n\r\n")
            return
        self._reply(b"HTTP/1.1 200 Connection Established\r\n\r\n")
        try:
            bytes_out, bytes_in = self._relay(upstream, cfg)
        finally:
            upstream.close()
        cfg.log({"event": "connect_complete", "connection_id": connection_id,
                 "host": host, "port": port, "allowed": True,
                 "bytes_out": bytes_out, "bytes_in": bytes_in})

    def _check_address_policy(self, host, port, cfg, event):
        try:
            cfg.allow.pinned_addresses(host, port)
        except (OSError, ValueError) as error:
            cfg.log({"event": event, "host": host, "port": port,
                     "allowed": False, "reason": f"address-policy: {error}"})
            self._reply(b"HTTP/1.1 403 Forbidden\r\nContent-Length: 0\r\n\r\n")
            return False
        return True

    def _relay(self, upstream, cfg) -> tuple[int, int]:
        upstream.settimeout(cfg.timeout)
        self.request.settimeout(cfg.timeout)
        client = self.request
        bytes_out = bytes_in = 0
        selector = selectors.DefaultSelector()
        selector.register(client, selectors.EVENT_READ, "client")
        selector.register(upstream, selectors.EVENT_READ, "upstream")
        try:
            while True:
                ready = selector.select(timeout=cfg.timeout)
                if not ready:
                    return bytes_out, bytes_in
                for key, _ in ready:
                    source = key.fileobj
                    destination = upstream if key.data == "client" else client
                    try:
                        data = source.recv(TUNNEL_BUF)
                    except OSError:
                        data = b""
                    if not data:
                        return bytes_out, bytes_in
                    try:
                        destination.sendall(data)
                    except OSError:
                        return bytes_out, bytes_in
                    if key.data == "client":
                        bytes_out += len(data)
                    else:
                        bytes_in += len(data)
        finally:
            selector.close()

    def _http(self, method: str, target: str, headers: dict, rest: bytes, cfg):
        if target.startswith("http://"):
            split = urllib.parse.urlsplit(target)
            host, port = self._parse_authority(split.netloc, 80)
            path = split.path or "/"
            if split.query:
                path += "?" + split.query
            if split.fragment:
                raise ValueError("fragment in destination URL is forbidden")
        elif target.startswith("/"):
            host_header = headers.get("host", "")
            host, port = self._parse_authority(host_header, 80)
            path = target
        else:
            raise ValueError("absolute-form HTTP requests must use http://")
        if not host:
            cfg.log({"event": "http", "allowed": False, "reason": "no-host"})
            self._reply(b"HTTP/1.1 400 Bad Request\r\nContent-Length: 0\r\n\r\n")
            return
        if not cfg.allow.allows(host, port):
            cfg.log({"event": "http", "host": host, "port": port,
                     "allowed": False, "reason": "not-in-allowlist"})
            self._reply(b"HTTP/1.1 403 Forbidden\r\nContent-Length: 0\r\n\r\n")
            return
        if "transfer-encoding" in headers:
            raise ValueError("Transfer-Encoding is unsupported")
        if not self._check_address_policy(host, port, cfg, "http"):
            return
        body = rest
        length_text = headers.get("content-length", "0")
        if not length_text.isdigit():
            raise ValueError("invalid Content-Length")
        length = int(length_text)
        if length > MAX_BODY:
            raise ValueError("request body too large")
        if len(body) > length:
            raise ValueError("unexpected bytes after request body")
        if length > len(body):
            while len(body) < length:
                chunk = self.request.recv(min(65536, length - len(body)))
                if not chunk:
                    raise ValueError("request body ended before Content-Length")
                body += chunk
        request = [f"{method} {path} HTTP/1.1"]
        for name, value in headers.items():
            if name not in HOP_HEADERS and name != "host":
                request.append(f"{name}: {value}")
        request.append(f"Host: {host}")
        request.append("Connection: close")
        payload = ("\r\n".join(request) + "\r\n\r\n").encode("latin-1") + body
        connection_id = uuid.uuid4().hex
        cfg.log({"event": "http_start", "connection_id": connection_id,
                 "host": host, "port": port, "allowed": True})
        upstream = None
        bytes_out = bytes_in = 0
        try:
            upstream = cfg.allow.connect(host, port, cfg.timeout)
            upstream.sendall(payload)
            bytes_out = len(payload)
            bytes_in = 0
            while True:
                data = upstream.recv(TUNNEL_BUF)
                if not data:
                    break
                self.request.sendall(data)
                bytes_in += len(data)
        except (OSError, ValueError) as exc:
            cfg.log({"event": "http_complete", "connection_id": connection_id,
                     "host": host, "port": port,
                     "allowed": True, "bytes_out": bytes_out, "bytes_in": bytes_in,
                     "reason": f"upstream-error: {exc}"})
            self._reply(b"HTTP/1.1 502 Bad Gateway\r\nContent-Length: 0\r\n\r\n")
            return
        finally:
            if upstream is not None:
                upstream.close()
        cfg.log({"event": "http_complete", "connection_id": connection_id,
                 "host": host, "port": port, "allowed": True,
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

    if not 1 <= args.timeout <= 60:
        parser.error("--timeout must be between 1 and 60 seconds")

    try:
        allowlist = Allowlist(args.allow)
    except ValueError as exc:
        parser.error(str(exc))
    log_lock = threading.Lock()
    log_file = open(args.log, "a", buffering=1, encoding="utf-8")

    def log(entry: dict):
        record = {"ts": time.time(), **entry}
        with log_lock:
            log_file.write(json.dumps(record, sort_keys=True) + "\n")

    if os.path.exists(args.socket):
        os.unlink(args.socket)
    server = ThreadingUnixServer(args.socket, Handler)
    os.chmod(args.socket, 0o600)
    server.cfg = SimpleNamespace(allow=allowlist, log=log, timeout=args.timeout)
    print(f"mandala-egress-proxy listening on {args.socket} "
          f"({len(allowlist.hosts) + len(allowlist.host_ports)} allowlist entries)",
          file=sys.stderr, flush=True)
    def stop_server(_signum, _frame):
        threading.Thread(target=server.shutdown, daemon=True).start()

    signal.signal(signal.SIGTERM, stop_server)
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
