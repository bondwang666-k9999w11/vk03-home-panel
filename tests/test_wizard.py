import os
from pathlib import Path
import tempfile
import time
import tkinter as tk
import unittest
from unittest.mock import Mock, patch

from vk03_config import read_config
from vk03_device_setup import DeviceWizard


@unittest.skipUnless(os.name == "nt", "Windows Tk UI")
class WizardTests(unittest.TestCase):
    def setUp(self):
        self.parent = tk.Tk()
        self.parent.withdraw()
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        self.saved = Mock()
        self.wizard = DeviceWizard(self.parent, self.root, self.saved)
        self.wizard.window.withdraw()

    def tearDown(self):
        if not self.wizard.closed:
            self.wizard.close()
        self.parent.destroy()
        self.temporary.cleanup()

    def connect(self):
        self.wizard.address.set("http://homeassistant.local:8123")
        self.wizard.token.set("test-only-credential")
        states = {"light.example_lamp": dict(state="off", attributes=dict(friendly_name="示例灯"))}
        with patch("vk03_device_setup.discover", return_value=states):
            self.wizard.connect()
            limit = time.monotonic() + 2
            while self.wizard.loading and time.monotonic() < limit:
                self.parent.update()
                time.sleep(.01)
        self.assertFalse(self.wizard.loading)
        self.assertIsNotNone(self.wizard.verified)

    def test_async_discovery_selection_and_encrypted_save(self):
        self.connect()
        choice = next(iter(self.wizard.lookup["light_1"]))
        self.wizard.selected["light_1"].set(choice)
        self.wizard.labels["light_1"].set("我的灯")
        self.wizard.save()
        data = read_config(self.root)
        self.assertEqual(data["bindings"]["light_1"], dict(entity_id="light.example_lamp", label="我的灯"))
        self.assertNotIn("test-only-credential", (self.root / "vk03_config.json").read_text(encoding="utf-8"))
        self.saved.assert_called_once()

    def test_changed_address_requires_reverification(self):
        self.connect()
        self.wizard.address.set("https://other.example")
        with patch("vk03_device_setup.messagebox.showerror") as error:
            self.wizard.save()
            error.assert_called_once()
        self.assertFalse((self.root / "vk03_config.json").exists())
        self.saved.assert_not_called()

    def test_unknown_entity_is_rejected_before_save(self):
        self.connect()
        self.wizard.selected["light_1"].set("light.not_present")
        with patch("vk03_device_setup.messagebox.showerror") as error:
            self.wizard.save()
            error.assert_called_once()
        self.assertFalse((self.root / "vk03_config.json").exists())


if __name__ == "__main__":
    unittest.main()
