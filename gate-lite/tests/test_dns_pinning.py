"""DNS authority controls use mocked resolution and sockets; no external traffic."""
import importlib.util
import pathlib
import socket
import unittest
from types import SimpleNamespace
from unittest import mock

path = pathlib.Path(__file__).resolve().parents[1] / "tools/mandala-egress-proxy.py"
spec = importlib.util.spec_from_file_location("egress_proxy_dns_tests", path)
proxy = importlib.util.module_from_spec(spec)
spec.loader.exec_module(proxy)


def resolved(address):
    return [(socket.AF_INET, socket.SOCK_STREAM, 6, "", (address, 0))]


class DnsPinningTests(unittest.TestCase):
    def test_dns_refusal_is_recorded_as_denial_before_any_upstream_socket(self):
        for event in ("connect", "http"):
            handler = object.__new__(proxy.Handler)
            handler._reply = mock.Mock()
            records = []
            cfg = SimpleNamespace(allow=proxy.Allowlist(["allowed.example"]), log=records.append, timeout=1)
            with mock.patch.object(proxy.socket, "getaddrinfo", return_value=resolved("127.0.0.1")):
                with mock.patch.object(proxy.socket, "socket", side_effect=AssertionError("no upstream socket")):
                    if event == "connect":
                        handler._connect("allowed.example:443", cfg)
                    else:
                        handler._http("GET", "http://allowed.example/", {}, b"", cfg)
            self.assertEqual(len(records), 1)
            self.assertFalse(records[0]["allowed"])
            self.assertTrue(records[0]["reason"].startswith("address-policy:"))
            self.assertIn(b"403 Forbidden", handler._reply.call_args.args[0])

    def test_host_is_resolved_once_and_numeric_connection_uses_frozen_set(self):
        allowed = proxy.Allowlist(["allowed.example:443"])
        upstream = mock.Mock()
        with mock.patch.object(proxy.socket, "getaddrinfo", side_effect=[resolved("8.8.8.8"), resolved("127.0.0.1")]) as lookup:
            with mock.patch.object(proxy.socket, "socket", return_value=upstream):
                allowed.connect("allowed.example", 443, 1)
                allowed.connect("allowed.example", 443, 1)
            self.assertEqual(lookup.call_count, 1)
            self.assertEqual(upstream.connect.call_args_list,
                             [mock.call(("8.8.8.8", 443)), mock.call(("8.8.8.8", 443))])

    def test_dns_cannot_grant_private_loopback_metadata_or_mixed_addresses(self):
        for address in ("127.0.0.1", "10.0.0.1", "169.254.169.254", "0.0.0.0", "224.0.0.1"):
            with self.subTest(address=address):
                allowed = proxy.Allowlist(["allowed.example"])
                with mock.patch.object(proxy.socket, "getaddrinfo", return_value=resolved(address)):
                    with self.assertRaises(ValueError):
                        allowed.pinned_addresses("allowed.example", 443)
        with mock.patch.object(proxy.socket, "getaddrinfo", return_value=resolved("8.8.8.8") + resolved("10.0.0.1")):
            with self.assertRaises(ValueError):
                proxy.Allowlist(["allowed.example"]).pinned_addresses("allowed.example", 443)

    def test_non_global_destination_requires_exact_literal_grant(self):
        with mock.patch.object(proxy.socket, "getaddrinfo", side_effect=AssertionError("literal must not use DNS")):
            addresses = proxy.Allowlist(["127.0.0.1:8080"]).pinned_addresses("127.0.0.1", 8080)
            self.assertEqual(str(addresses[0]), "127.0.0.1")
            with self.assertRaises(ValueError):
                proxy.Allowlist(["127.0.0.1:8080"]).pinned_addresses("127.0.0.1", 8081)
