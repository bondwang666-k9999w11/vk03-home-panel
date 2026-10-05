import io
import json
import unittest
from unittest.mock import patch
import urllib.error

from vk03_device_setup import discover, choices, NoRedirect


class DiscoveryTests(unittest.TestCase):
    def test_get_only_and_domain_filtering(self):
        response = io.BytesIO(json.dumps([
            dict(entity_id="light.example_lamp", attributes=dict(friendly_name="演示灯")),
            dict(entity_id="switch.example_switch", attributes={}),
            dict(entity_id="sensor.example_temperature", attributes={}),
            dict(entity_id="fan.example_purifier", attributes={}),
        ]).encode())
        with patch("urllib.request.build_opener") as opener:
            opener.return_value.open.return_value = response
            states = discover("http://homeassistant.local:8123", "test-only-credential")
            request = opener.return_value.open.call_args.args[0]
            self.assertEqual(request.get_method(), "GET")
            self.assertEqual(request.full_url, "http://homeassistant.local:8123/api/states")
        self.assertEqual(set(choices(states, "light_1").values()), {"light.example_lamp", "switch.example_switch"})
        self.assertEqual(set(choices(states, "purifier").values()), {"fan.example_purifier"})

    def test_errors_do_not_echo_response_or_token(self):
        error = urllib.error.HTTPError("http://homeassistant.local", 401, "private response", {}, io.BytesIO(b"private response"))
        with patch("urllib.request.build_opener") as opener:
            opener.return_value.open.side_effect = error
            with self.assertRaises(ValueError) as caught:
                discover("http://homeassistant.local:8123", "test-only-credential")
        self.assertNotIn("test-only-credential", str(caught.exception))
        self.assertNotIn("private response", str(caught.exception))

    def test_redirect_is_refused(self):
        self.assertIsNone(NoRedirect().redirect_request(None, None, 302, "", {}, "https://other.example"))


if __name__ == "__main__":
    unittest.main()
