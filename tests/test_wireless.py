import threading
import unittest
from unittest.mock import patch

from mirror.backend import connect_wifi, prepare_wifi, validate_endpoint


class WirelessConnectionTests(unittest.TestCase):
    endpoint = "192.0.2.8:45678"
    target = endpoint + "\tTCP\tConnected\tlocalhost\thdc"

    def test_existing_connection_reuses_exact_target(self):
        with patch("mirror.backend.hdc", return_value=self.target) as hdc:
            self.assertEqual(connect_wifi(self.endpoint, threading.Event()), self.endpoint)
        hdc.assert_called_once_with("list", "targets", "-v", timeout=4)

    def test_waits_for_requested_target_after_repeat_response(self):
        others = "usb1 USB Connected localhost hdc\n192.0.2.8:5555 TCP Connected localhost hdc"
        replies = [others, "[Info]Target is connected, repeat operation.", others, self.target]
        with patch("mirror.backend.hdc", side_effect=replies) as hdc:
            self.assertEqual(connect_wifi(self.endpoint, threading.Event()), self.endpoint)
        self.assertEqual(hdc.call_args_list[1].args, ("tconn", self.endpoint))

    def test_failed_connection_does_not_fall_back_to_another_phone(self):
        other = "192.0.2.9:45678 TCP Connected localhost hdc"
        with patch("mirror.backend.hdc", side_effect=[other, "[Fail]Connect failed.", other]):
            with self.assertRaisesRegex(RuntimeError, self.endpoint):
                connect_wifi(self.endpoint, threading.Event())

    def test_invalid_endpoint_never_runs_hdc(self):
        with patch("mirror.backend.hdc") as hdc:
            for value in ("", "phone:5555", "192.0.2.8:0", "192.0.2.8:65536"):
                with self.subTest(value=value), self.assertRaises(ValueError):
                    connect_wifi(value, threading.Event())
        hdc.assert_not_called()
        self.assertEqual(validate_endpoint(" 192.0.2.8:045678 "), self.endpoint)

    def test_usb_setup_uses_the_selected_phone(self):
        with patch("mirror.backend.hdc", side_effect=[
            "inet addr:192.0.2.8  Mask:255.255.255.0", "Set device run mode successful.",
        ]) as hdc:
            self.assertEqual(prepare_wifi("usb1"), "192.0.2.8:5555")
        self.assertEqual(hdc.call_args_list[1].args, ("-t", "usb1", "tmode", "port", "5555"))
