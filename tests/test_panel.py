"""Execute only drawing/control helpers, never top-level USB initialization."""
import ast
from datetime import datetime
import hashlib
from pathlib import Path
import unittest

from vk03_appearance_editor import preview_renderer
from vk03_config import demo_bindings
from vk03_monitor import draw_monitor
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]


class PanelTests(unittest.TestCase):
    def setUp(self):
        self.ns = preview_renderer(ROOT)
    def tearDown(self):
        self.ns["appearance"].close()

    def test_generic_light_domains_and_fan_presets(self):
        ns = self.ns
        snapshot = ns["snapshot"]
        for role, entity in ns["LIGHT_ENTITIES"].items():
            self.assertEqual(ns["build_command"](role, snapshot, "cool"), ("light", "toggle", {"entity_id": entity}))
        entity = ns["LIGHT_ENTITIES"]["light_1"]
        ns["LIGHT_ENTITIES"]["light_1"] = "switch.example_switch"
        snapshot["entities"]["switch.example_switch"] = snapshot["entities"][entity]
        self.assertEqual(ns["build_command"]("light_1", snapshot, "cool")[0], "switch")
        fan = ns["PURIFIER_ENTITY"]
        self.assertEqual(ns["build_command"]("purifier_preset:睡眠", snapshot, "cool"),
                         ("fan", "set_preset_mode", {"entity_id": fan, "preset_mode": "睡眠"}))
        with self.assertRaises(ValueError):
            ns["build_command"]("purifier_preset:unsupported", snapshot, "cool")

    def test_percentage_and_capability_gate(self):
        ns = self.ns
        fan = ns["PURIFIER_ENTITY"]
        ns["snapshot"]["entities"][fan] = dict(state="on", attributes=dict(supported_features=49, percentage=50, percentage_step=10))
        self.assertEqual(ns["build_command"]("purifier_speed_up", ns["snapshot"], "cool"),
                         ("fan", "set_percentage", {"entity_id": fan, "percentage": 60}))
        ns["snapshot"]["entities"][fan]["attributes"]["supported_features"] = 48
        with self.assertRaises(ValueError):
            ns["build_command"]("purifier_speed_up", ns["snapshot"], "cool")

    def test_temperature_native_units_and_bounds(self):
        ns = self.ns
        entity = ns["AC_ENTITY"]
        ns["snapshot"]["unit"] = "°F"
        ns["snapshot"]["entities"][entity]["attributes"].update(temperature=79, min_temp=61, max_temp=88, target_temp_step=.5)
        command = ns["build_command"]("temp_up", ns["snapshot"], "cool")
        self.assertEqual(command[2]["temperature"], 81)
        self.assertAlmostEqual(ns["to_celsius"](79, "°F"), 26.1111111111)
        ns["snapshot"]["entities"][entity]["attributes"]["temperature"] = 88
        with self.assertRaises(ValueError):
            ns["build_command"]("temp_up", ns["snapshot"], "cool")

    def test_navigation_and_unsupported_controls(self):
        ns = self.ns
        ns["page"] = "home"
        ns["render_overlay"]()
        self.assertIn("monitor_home", [button["name"] for button in ns["buttons"]])
        ns["handle_action"]("monitor_home")
        self.assertEqual(ns["page"], "monitor")
        self.assertTrue(ns["ha_commands"].empty())
        for page in ("ac", "purifier"):
            ns["page"] = page
            ns["handle_action"]("back")
            self.assertEqual(ns["page"], "home")
        ns["page"] = "ac"
        ns["snapshot"]["entities"][ns["AC_ENTITY"]]["attributes"]["supported_features"] = 0
        ns["render_overlay"]()
        actions = [button["name"] for button in ns["buttons"]]
        self.assertNotIn("temp_up", actions)
        self.assertNotIn("ac_fan", actions)
        self.assertNotIn("ac_swing", actions)

    def test_empty_config_disables_all_devices(self):
        ns = self.ns
        ns["LIGHT_ENTITIES"] = dict.fromkeys(ns["LIGHT_ENTITIES"], "")
        ns["AC_ENTITY"] = ns["PURIFIER_ENTITY"] = ""
        ns["ENV_ENTITIES"] = dict.fromkeys(ns["ENV_ENTITIES"], "")
        ns["snapshot"]["entities"][""] = dict(state=None, attributes={})
        ns["page"] = "home"
        ns["render_overlay"]()
        self.assertEqual([button["name"] for button in ns["buttons"]], ["monitor_home"])

    def test_deep_light_opacity_glow_and_overlay_cache(self):
        ns = self.ns
        ns["page"] = "home"
        ns["appearance"].apply(dict(button_mode="light", button_opacity=100))
        ns["render_ui"]()
        old = ns["_overlay_image"]
        ns["appearance"].apply(dict(button_mode="dark", button_opacity=100))
        ns["render_ui"]()
        self.assertIsNot(old, ns["_overlay_image"])
        self.assertNotEqual(old.getpixel((30, 145)), ns["_overlay_image"].getpixel((30, 145)))
        for mode in ("light", "dark"):
            ns["appearance"].apply(dict(button_mode=mode, button_opacity=0))
            self.assertEqual(ns["render_overlay"]().getpixel((30, 145))[3], 0)
        monitor = Image.new("RGBA", (960, 360))
        draw_monitor(monitor, dict(cpu_temp=40, gpu_temp=38), ns["load_font"], {}, datetime(2026, 10, 5, 12, 0, 0))
        self.assertIsNone(monitor.getchannel("A").crop((300, 90, 760, 350)).getbbox())

    def test_stable_hardware_functions(self):
        # Hashes recorded from the user-tested formal hardware implementation.
        import json
        expected = json.loads((ROOT / "tests" / "hardware-hashes.json").read_text())
        tree = ast.parse((ROOT / "vk03_home_panel_daily.py").read_text(encoding="utf-8"))
        for name, digest in expected.items():
            node = next(node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name == name)
            actual = hashlib.sha256(ast.dump(node, include_attributes=False).encode()).hexdigest()
            self.assertEqual(actual, digest, name)


if __name__ == "__main__":
    unittest.main()
