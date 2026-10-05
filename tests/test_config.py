import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from vk03_config import (normalize_bindings, empty_bindings, validate_url, save_config,
                         read_config, configured, encrypt_token, decrypt_token)


class ConfigurationTests(unittest.TestCase):
    def test_domains_optional_and_duplicate_controls(self):
        result = normalize_bindings({})
        self.assertTrue(all(not entry["entity_id"] for entry in result.values()))
        bindings = empty_bindings()
        bindings["light_1"]["entity_id"] = "light.example_lamp"
        self.assertEqual(normalize_bindings(bindings)["light_1"]["entity_id"], "light.example_lamp")
        bindings["light_2"]["entity_id"] = "light.example_lamp"
        with self.assertRaises(ValueError):
            normalize_bindings(bindings)
        bindings["light_2"]["entity_id"] = "sensor.example_wrong_domain"
        with self.assertRaises(ValueError):
            normalize_bindings(bindings)

    def test_url_validation(self):
        self.assertEqual(validate_url(" http://homeassistant.local:8123/ "), "http://homeassistant.local:8123")
        for address in ("file:///tmp", "http://user:pass@localhost", "http://localhost?q=1", "http://localhost/#a", "http://localhost:bad"):
            with self.assertRaises(ValueError):
                validate_url(address)

    def test_atomic_save_has_no_plain_token_and_preserves_bindings(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            with patch("vk03_config.encrypt_token", return_value="synthetic-encrypted-test-data"):
                save_config(root, "http://homeassistant.local:8123", "test-only-secret", empty_bindings())
            text = (root / "vk03_config.json").read_text(encoding="utf-8")
            self.assertNotIn("test-only-secret", text)
            self.assertEqual(read_config(root)["schema_version"], 1)
            self.assertTrue(configured(root))
            self.assertFalse((root / "vk03_config.pending.json").exists())
            original = text
            with self.assertRaises(ValueError):
                save_config(root, "not-a-url", "test-only-secret", {})
            self.assertEqual((root / "vk03_config.json").read_text(encoding="utf-8"), original)

    @unittest.skipUnless(os.name == "nt", "DPAPI is Windows-only")
    def test_dpapi_roundtrip(self):
        protected = encrypt_token("test-only-credential")
        self.assertNotEqual(protected, "test-only-credential")
        self.assertEqual(decrypt_token(protected), "test-only-credential")


if __name__ == "__main__":
    unittest.main()
